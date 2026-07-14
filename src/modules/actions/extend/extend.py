import logging
import copy
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from collections.abc import Callable
from typing import Any, Optional, Tuple

from oci.exceptions import ServiceError
from oci.identity.models import (
    BulkEditTagsDetails,
    BulkEditOperationDetails,
    BulkEditResource,
)
from ..action import BaseAction
from ..types import ActionKind, ActionStrategy, BaseResourceType
from ..result import Result


class Extender(BaseAction):
    # Extender is the web-facing entry point for expiry/tag extension requests.
    # It discovers BaseResourceType plugins from actions/types/ and delegates
    # resource-specific behavior to those classes.
    ACTION_KIND = ActionKind.EXTEND
    ACTION_SPEC_MODULES = ("modules.actions.types",)

    def __init__(
        self,
        config,
        signer,
        tag_namespace,
        tag_key,
        extend_period=timedelta(days=30),
        handler: logging.Handler | None = None,
        log_level: int | str = logging.INFO,
        regions=None,
        signer_factory: Callable[[str | None], Any] | None = None,
    ):
        super().__init__(
            config=config,
            signer=signer,
            handler=handler or logging.StreamHandler(),
            log_level=log_level,
            regions=regions,
            signer_factory=signer_factory,
            logger_name=__name__,
            require_region_without_regions=False,
            require_signer_for_regions=True,
            signer_required_message=(
                "signer_factory is required when creating extend clients "
                "for multiple regions"
            ),
        )
        self.tag_namespace = tag_namespace
        self.tag_key = tag_key
        self.extend_period = extend_period
        self.logger.info("Unified Extender initialized")

    def extend(self, resource: dict) -> Result:
        ocid = resource.get("identifier")
        rtype = resource.get("resource_type", "")
        defined_tags = resource.get("defined_tags", {})
        today = datetime.now(timezone.utc).date()
        new_value = (today + self.extend_period).strftime("%Y-%m-%d")
        # Lookup is normalized, so aliases declared by a plugin resolve to the
        # same BaseResourceType class.
        resource_type = type(self).get_resource_type(rtype)
        if not resource_type:
            self.logger.error("No extend implementation for %s (%s)", rtype, ocid)
            return Result(
                HTTPStatus.NOT_IMPLEMENTED,
                message=f"No extender implementation for {rtype}",
                metadata={"identifier": ocid, "resource_type": rtype},
        )
        # Extender owns strategy dispatch; resource types own resource-specific
        # hooks and payload construction.
        return self._extend_resource(
            resource_type(),
            resource,
            None,
            new_value,
            defined_tags,
        )

    def _extend_resource(
        self,
        resource_type,
        resource,
        region,
        new_value,
        defined_tags,
    ) -> Result:
        resource = {**resource, "resource_type": resource_type.resource_type}
        ocid = resource.get("identifier")
        rtype = resource_type.resource_type
        region = resource_type._region(self, resource, region)
        if not region:
            return Result(
                HTTPStatus.BAD_REQUEST,
                message=f"Region missing for {rtype} {ocid}",
                metadata={"identifier": ocid, "resource_type": rtype},
            )
        if region not in self.clients:
            return Result(
                HTTPStatus.NOT_FOUND,
                message=f"No client configured for region {region}",
                metadata={"identifier": ocid, "resource_type": rtype, "region": region},
            )

        if type(resource_type).extend is not BaseResourceType.extend:
            return resource_type.extend(self, resource, region, new_value, defined_tags)

        if resource_type.extend_strategy == ActionStrategy.EXTEND_BULK_TAG:
            bulk_result, bulk_success = self._try_bulk_extend(
                resource,
                region,
                new_value,
            )
            if bulk_success and bulk_result:
                self.logger.info("Bulk extend succeeded for %s (%s)", rtype, ocid)
                bulk_result.metadata.setdefault("method", "bulk")
                return bulk_result
            self.logger.error(
                "Bulk supported resource failed via bulk extend: %s (%s)",
                rtype,
                ocid,
            )
            return bulk_result or Result(
                HTTPStatus.NOT_IMPLEMENTED,
                message=f"Bulk extend failed for {rtype} {ocid}",
                metadata={"identifier": ocid, "resource_type": rtype},
            )

        if resource_type.extend_strategy == ActionStrategy.EXTEND_SDK_TAG:
            try:
                if type(resource_type).extend_sdk_tag is not BaseResourceType.extend_sdk_tag:
                    response = resource_type.extend_sdk_tag(
                        self,
                        resource,
                        region,
                        new_value,
                        defined_tags,
                    )
                else:
                    response = self._extend_sdk_tag(
                        resource_type,
                        resource,
                        region,
                        new_value,
                        defined_tags,
                    )
                status = getattr(response, "status", response)
                return Result(
                    status=status,
                    message=f"Expiry extended to {new_value}",
                    metadata={
                        "identifier": ocid,
                        "resource_type": rtype,
                        "region": region,
                        "method": "sdk",
                    },
                )
            except NotImplementedError:
                self.logger.error("No extend implementation for %s (%s)", rtype, ocid)
                return Result(
                    HTTPStatus.NOT_IMPLEMENTED,
                    message=f"No extender implementation for {rtype}",
                    metadata={"identifier": ocid, "resource_type": rtype},
                )
            except Exception:
                self.logger.exception("SDK extend failed for %s (%s)", rtype, ocid)
                return Result(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    message=f"SDK extend failed for {rtype} {ocid}",
                    metadata={
                        "identifier": ocid,
                        "resource_type": rtype,
                        "region": region,
                        "method": "sdk",
                    },
                )

        return Result(
            HTTPStatus.NOT_IMPLEMENTED,
            message=f"No extender implementation for {rtype}",
            metadata={"identifier": ocid, "resource_type": rtype},
        )

    def _merge_tags(self, defined_tags, new_value):
        tags = copy.deepcopy(defined_tags) if defined_tags else {}
        tags.setdefault(self.tag_namespace, {})
        tags[self.tag_namespace][self.tag_key] = new_value
        return tags

    def _extend_sdk_tag(self, resource_type, resource, region, new_value, defined_tags):
        if not all(
            (
                resource_type.extend_client_attr,
                resource_type.extend_method_name,
                resource_type.extend_identifier_param,
                resource_type.extend_details_param,
                resource_type.extend_details_cls,
            )
        ):
            raise NotImplementedError(
                f"No SDK tag update metadata configured for {resource_type.resource_type}"
            )

        client = getattr(self.clients[region], resource_type.extend_client_attr)
        method = getattr(client, resource_type.extend_method_name)
        details = resource_type.extend_details_cls(
            defined_tags=self._merge_tags(defined_tags, new_value)
        )
        return method(
            **{
                resource_type.extend_identifier_param: resource["identifier"],
                resource_type.extend_details_param: details,
            }
        )

    def _try_bulk_extend(self, resource, region, new_value) -> Tuple[Optional[Result], bool]:
        ocid = resource.get("identifier")
        rtype = resource.get("resource_type")
        compartment_id = resource.get("compartment_id")
        action_region = None
        if not compartment_id:
            self.logger.error(
                "Missing compartment_id for bulk extend %s (%s)",
                rtype, ocid
            )
            return (
                Result(
                    HTTPStatus.BAD_REQUEST,
                    message=f"Missing compartment_id for {ocid}",
                    metadata={"identifier": ocid, "resource_type": rtype},
                ),
                False,
            )
        try:
            bulk_resource = BulkEditResource(
                id=resource["identifier"],
                resource_type=resource["resource_type"],
                metadata={}
            )
            bulk_operation = BulkEditOperationDetails(
                operation_type="ADD_OR_SET",
                defined_tags={
                    self.tag_namespace: {
                        self.tag_key: new_value
                    }
                }
            )
            details = BulkEditTagsDetails(
                compartment_id=resource["compartment_id"],
                resources=[bulk_resource],
                bulk_edit_operations=[bulk_operation],
            )
            action_region, action_clients = self._get_home_region_client_bundle()
            response = action_clients.identity_client.bulk_edit_tags(
                bulk_edit_tags_details=details
            )
            status = getattr(response, "status", HTTPStatus.OK)
            headers = getattr(response, "headers", {}) or {}
            work_request = headers.get("opc-work-request-id")
            return (
                Result(
                    status=status,
                    work_request=work_request,
                    message=f"Expiry extended to {new_value}",
                    metadata={
                        "identifier": ocid,
                        "resource_type": rtype,
                        "region": region,
                        "action_region": action_region,
                        "method": "bulk",
                    },
                ),
                True,
            )
        except ServiceError as e:
            self.logger.info(
                "Bulk extend rejected by OCI for %s (%s): %s",
                rtype, ocid, e.message
            )
            return (
                Result(
                    status=e.status or HTTPStatus.BAD_REQUEST,
                    message=e.message,
                    metadata={
                        "identifier": ocid,
                        "resource_type": rtype,
                        "region": region,
                        "action_region": action_region or region,
                        "method": "bulk",
                    },
                ),
                False,
            )
        except Exception:
            self.logger.exception(
                "Bulk extend crashed for %s (%s)",
                rtype, ocid
            )
            return (
                Result(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    message=f"Bulk extend crashed for {ocid}",
                    metadata={
                        "identifier": ocid,
                        "resource_type": rtype,
                        "region": region,
                        "action_region": action_region or region,
                        "method": "bulk",
                    },
                ),
                False,
            )
