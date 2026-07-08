#!/usr/bin/python3.11
import logging
from http import HTTPStatus
from collections.abc import Callable
from typing import Any, Dict, Optional, Tuple
from oci import Signer
from oci.identity.models import BulkMoveResourcesDetails
from oci.exceptions import ServiceError
from ..action import BaseAction
from ..types import ActionKind, ActionStrategy
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
        # BaseResourceType.delete() owns strategy dispatch and can be overridden by
        # a plugin for one-off OCI behavior.
        return resource_type().delete(self, resource, region, target)

    def _try_bulk_one(
        self, resource, region, target
    ) -> Tuple[Optional[Result], bool]:
        action_region = None
        try:
            rtype = resource["resource_type"]
            ocid = resource["identifier"]

            bulk_resource = {
                "entityType": rtype,
                "identifier": ocid,
            }

            # Buckets need metadata
            if rtype == "Bucket":
                namespace = (
                    resource.get("namespace")
                    or resource.get("namespace_name")
                    or self.clients[region]
                    .object_storage_client.get_namespace()
                    .data
                )

                bucket_name = (
                    resource.get("identifier_name")
                    or resource.get("display_name")
                    or resource.get("bucket_name")
                )

                if not bucket_name:
                    self.logger.error("Bucket name missing for %s", ocid)
                    return (
                        Result(
                            status=HTTPStatus.BAD_REQUEST,
                            message=f"Bucket name missing for {ocid}",
                            metadata={
                                "method": "bulk",
                                "resource_type": rtype,
                                "identifier": ocid,
                                "region": region,
                            },
                        ),
                        False,
                    )

                bulk_resource["metadata"] = {
                    "namespaceName": namespace,
                    "bucketName": bucket_name,
                }

                self.logger.info(
                    "Bulk bucket payload → ocid=%s name=%s namespace=%s",
                    ocid,
                    bucket_name,
                    namespace,
                )

            details = BulkMoveResourcesDetails(
                target_compartment_id=target,
                resources=[bulk_resource],
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

        except ServiceError as e:
            rtype = resource.get("resource_type")
            ocid = resource.get("identifier")
            self.logger.info(
                "Bulk move rejected by OCI for %s (%s): %s",
                rtype,
                ocid,
                e.message,
            )
            return (
                Result(
                    status=e.status or HTTPStatus.BAD_REQUEST,
                    message=e.message,
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

        except Exception:
            rtype = resource.get("resource_type")
            ocid = resource.get("identifier")
            self.logger.exception("Bulk move crashed for %s", ocid)
            return (
                Result(
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    message=f"Bulk move crashed for {ocid}",
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

    def _move_with_sdk_spec(
        self,
        move_spec: tuple[str, str],
        identifier,
        region,
        target_compartment_id,
    ) -> Any:
        client_attr, method_name = move_spec
        client = getattr(self.clients[region], client_attr)
        method = getattr(client, method_name)
        return method(identifier, {"compartmentId": target_compartment_id})
