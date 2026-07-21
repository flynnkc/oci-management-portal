#!/usr/bin/python3.11
from http import HTTPStatus

from oci.logging.models import UpdateLogDetails

from .base import ActionStrategy, BaseResourceType
from ..result import Result


class LogResource(BaseResourceType):
    resource_type = 'Log'
    aliases = ('log', 'logs')
    delete_strategy = ActionStrategy.DELETE_FORCE
    extend_strategy = ActionStrategy.EXTEND_IDENTITY

    def _log_group_id(self, resource) -> str | None:
        additional_details = (
            resource.get("additional_details")
            or resource.get("additionalDetails")
            or {}
        )
        return (
            resource.get("log_group_id")
            or resource.get("logGroupId")
            or additional_details.get("log_group_id")
            or additional_details.get("logGroupId")
        )

    def force_delete(self, deleter, resource) -> Result:
        log_group_id = self._log_group_id(resource)
        if not log_group_id:
            return Result(
                HTTPStatus.BAD_REQUEST,
                message=f"Missing log_group_id for {resource.get('identifier')}",
                metadata={
                    "method": "force",
                    "resource_type": self.resource_type,
                    "identifier": resource.get("identifier"),
                },
            )

        region = self._region(deleter, resource)
        if not region:
            return Result(
                HTTPStatus.BAD_REQUEST,
                message=f"Region missing for {self.resource_type} {resource.get('identifier')}",
                metadata={
                    "method": "force",
                    "resource_type": self.resource_type,
                    "identifier": resource.get("identifier"),
                    "log_group_id": log_group_id,
                },
            )

        response = deleter.clients[region].logging_management_client.delete_log(
            log_group_id=log_group_id,
            log_id=resource["identifier"],
        )
        status = getattr(response, "status", HTTPStatus.OK)
        headers = getattr(response, "headers", {}) or {}
        return Result(
            status=status,
            work_request=headers.get("opc-work-request-id"),
            metadata={
                "method": "force",
                "resource_type": self.resource_type,
                "identifier": resource["identifier"],
                "region": region,
                "log_group_id": log_group_id,
            },
        )

    def extend(self, extender, resource, region, new_value, defined_tags) -> Result:
        log_group_id = self._log_group_id(resource)
        if not log_group_id:
            return Result(
                HTTPStatus.BAD_REQUEST,
                message=f"Missing log_group_id for {resource.get('identifier')}",
                metadata={
                    "identifier": resource.get("identifier"),
                    "resource_type": self.resource_type,
                },
            )

        response = extender.clients[region].logging_management_client.update_log(
            log_group_id=log_group_id,
            log_id=resource["identifier"],
            update_log_details=UpdateLogDetails(
                defined_tags=self._merge_tags(extender, defined_tags, new_value),
                freeform_tags=(
                    resource.get("freeform_tags")
                    or resource.get("freeformTags")
                    or {}
                ),
            ),
        )
        status = getattr(response, "status", HTTPStatus.OK)
        return Result(
            status=status,
            message=f"Expiry extended to {new_value}",
            metadata={
                "identifier": resource["identifier"],
                "resource_type": self.resource_type,
                "region": region,
                "method": "sdk",
                "log_group_id": log_group_id,
            },
        )
