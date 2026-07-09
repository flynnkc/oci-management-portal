#!/usr/bin/python3.11
import logging
from http import HTTPStatus
from collections.abc import Callable
from typing import Dict, Optional, Tuple
from oci import Signer
from oci.identity.models import BulkMoveResourcesDetails
from ..action import BaseAction
from ..types import ActionKind, ActionStrategy, BaseResourceType
from ..result import Result


class Deleter(BaseAction):
    # Deleter is the web-facing entry point for delete requests. It discovers
    # BaseResourceType plugins from actions/types/ and delegates resource-specific
    # behavior to those classes.
    ACTION_KIND = ActionKind.DELETE
    ACTION_SPEC_MODULES = ("modules.actions.types",)

    @classmethod
    def supported_delete_display_map(cls) -> dict[str, str]:
        """
        Returns {normalized_key: display_name} for all Delete-supported resource types.
        """
        return cls.supported_display_map()

    @classmethod
    def supported_force_display_map(cls) -> dict[str, str]:
        """
        Returns {normalized_key: display_name} for force-delete resource types only.
        """
        return {
            cls.normalize_resource_type(spec.resource_type): spec.label
            for spec in cls.action_specs()
            if spec.strategy == ActionStrategy.DELETE_FORCE
        }

    @classmethod
    def force_delete_norm_keys(cls) -> set[str]:
        return cls.supported_strategy_norm_keys(ActionStrategy.DELETE_FORCE)

    def __init__(
        self,
        config: dict[str, str],
        quarantine_cmp: str,
        signer: Signer | None,
        handler: logging.Handler | None = None,
        log_level: int | str = logging.INFO,
        regions=None,
        signer_factory: Callable[[str | None], Signer] | None = None,
    ):
        super().__init__(
            config=config,
            signer=signer,
            handler=handler or logging.StreamHandler(),
            log_level=log_level,
            regions=regions,
            signer_factory=signer_factory,
            logger_name=__name__,
            require_region_without_regions=True,
            signer_required_message=(
                "signer_factory is required when creating delete clients "
                "for multiple regions"
            ),
        )
        self.quarantine_cmp = quarantine_cmp

        self.logger.info("Deleter initialized")

    # Delete is the entry point to this class, intended to either move the resource
    # to a compartment to await deletion, or force/bulk delete depending on the type
    def delete(self, resource: Dict, **kwargs) -> Result:
        region = kwargs.get("region")
        target = kwargs.get("target_compartment_id", self.quarantine_cmp)
        return self._delete_single(resource, region, target)

    def _delete_single(self, resource, region, target) -> Result:
        rtype = resource.get("resource_type")
        ocid = resource.get("identifier")
        # Lookup is normalized, so resource_type aliases declared by a plugin
        # resolve to the same BaseResourceType class.
        resource_type = type(self).get_resource_type(rtype)
        if not resource_type:
            self.logger.error("No delete implementation for %s (%s)", rtype, ocid)
            return Result(
                HTTPStatus.NOT_IMPLEMENTED,
                message=f"No deleter implementation for {rtype}",
                metadata={"resource_type": rtype, "identifier": ocid},
        )
        # Deleter owns strategy dispatch; resource types own resource-specific
        # hooks and payload construction.
        return self._delete_resource(resource_type(), resource, region, target)

    def _delete_resource(self, resource_type, resource, region, target) -> Result:
        resource = {**resource, "resource_type": resource_type.resource_type}
        rtype = resource_type.resource_type
        ocid = resource.get("identifier")
        metadata = {
            "resource_type": rtype,
            "identifier": ocid,
        }
        last_error: Result | None = None

        if type(resource_type).delete is not BaseResourceType.delete:
            return resource_type.delete(self, resource, region, target)

        if resource_type.delete_strategy == ActionStrategy.DELETE_FORCE:
            try:
                result = resource_type.force_delete(self, resource)
                self.logger.info("Force delete succeeded for %s (%s)", rtype, ocid)
                return result
            except Exception as exc:
                self.logger.exception("Force delete failed for %s (%s)", rtype, ocid)
                return Result(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    message=str(exc),
                    metadata={"method": "force", **metadata},
                )

        region = resource_type._region(self, resource, region)
        if not region:
            return Result(
                HTTPStatus.BAD_REQUEST,
                message=f"Region missing for {rtype} {ocid}",
                metadata=metadata,
            )
        if region not in self.clients:
            return Result(
                HTTPStatus.NOT_FOUND,
                message=f"No client configured for region {region}",
                metadata={"resource_type": rtype, "identifier": ocid, "region": region},
            )

        metadata["region"] = region

        if resource_type.delete_strategy == ActionStrategy.DELETE_BULK_MOVE:
            bulk_result, bulk_success = self._delete_bulk_move(
                resource_type,
                resource,
                region,
                target,
            )
            if bulk_success and bulk_result:
                self.logger.info("Bulk move succeeded for %s (%s)", rtype, ocid)
                bulk_result.metadata.update({"method": "bulk", **metadata})
                return bulk_result

            if bulk_result:
                last_error = bulk_result
            self.logger.error(
                "Bulk supported resource failed via bulk: %s (%s)", rtype, ocid
            )

        if resource_type.delete_strategy == ActionStrategy.DELETE_SDK_MOVE:
            if resource_type.delete_client_attr and resource_type.delete_method_name:
                try:
                    response = self._delete_sdk_move(
                        resource_type,
                        resource,
                        region,
                        target,
                    )
                    self.logger.info("SDK move succeeded for %s (%s)", rtype, ocid)
                    status = getattr(response, "status", HTTPStatus.OK)
                    headers = getattr(response, "headers", {}) or {}
                    work_request = headers.get("opc-work-request-id")
                    return Result(
                        status=status,
                        work_request=work_request,
                        metadata={"method": "sdk", **metadata},
                    )
                except Exception:
                    self.logger.exception("SDK move failed for %s (%s)", rtype, ocid)
                    last_error = Result(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        message=f"SDK move failed for {rtype} {ocid}",
                        metadata={"method": "sdk", **metadata},
                    )

        self.logger.error("Delete failed after all attempts for %s (%s)", rtype, ocid)
        return last_error or Result(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            message=f"Delete failed after all attempts for {rtype} {ocid}",
            metadata=metadata,
        )

    def _delete_bulk_move(
        self,
        resource_type,
        resource,
        region,
        target,
    ) -> Tuple[Optional[Result], bool]:
        action_region = None
        rtype = resource.get("resource_type")
        ocid = resource.get("identifier")
        try:
            details = self.bulk_move_details(
                target,
                [resource_type.delete_bulk_resource(self, resource, region)],
            )
            action_region, action_clients = self._get_home_region_client_bundle()
            response = action_clients.identity_client.bulk_move_resources(
                resource["compartment_id"], details
            )

            headers = getattr(response, "headers", {}) or {}
            work_request = headers.get("opc-work-request-id")
            return (
                Result(
                    status=response.status,
                    work_request=work_request,
                    metadata={
                        "method": "bulk",
                        "resource_type": rtype,
                        "identifier": ocid,
                        "region": region,
                        "action_region": action_region,
                    },
                ),
                True,
            )
        except Exception as exc:
            if isinstance(exc, ValueError):
                status = HTTPStatus.BAD_REQUEST
            else:
                status = getattr(exc, "status", HTTPStatus.INTERNAL_SERVER_ERROR)
            message = getattr(exc, "message", f"Bulk move crashed for {ocid}")
            if status == HTTPStatus.INTERNAL_SERVER_ERROR:
                self.logger.exception("Bulk move crashed for %s", ocid)
            else:
                self.logger.info(
                    "Bulk move rejected by OCI for %s (%s): %s",
                    rtype,
                    ocid,
                    message,
                )
            return (
                Result(
                    status=status or HTTPStatus.BAD_REQUEST,
                    message=message,
                    metadata={
                        "method": "bulk",
                        "resource_type": rtype,
                        "identifier": ocid,
                        "region": region,
                        "action_region": action_region or region,
                    },
                ),
                False,
            )

    def _delete_sdk_move(self, resource_type, resource, region, target):
        if not resource_type.delete_client_attr or not resource_type.delete_method_name:
            raise NotImplementedError(
                f"No SDK move metadata configured for {resource_type.resource_type}"
            )

        client = getattr(self.clients[region], resource_type.delete_client_attr)
        method = getattr(client, resource_type.delete_method_name)
        return method(resource["identifier"], {"compartmentId": target})

    def bulk_move_details(self, target, resources) -> BulkMoveResourcesDetails:
        return BulkMoveResourcesDetails(
            target_compartment_id=target,
            resources=resources,
        )
