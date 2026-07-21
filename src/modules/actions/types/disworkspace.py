#!/usr/bin/python3.11
from http import HTTPStatus

from oci.data_integration.models import UpdateWorkspaceDetails

from .base import ActionStrategy, BaseResourceType
from ..result import Result


class DISWorkspaceResource(BaseResourceType):
    resource_type = 'DISWorkspace'
    aliases = ('disworkspace', 'dis_workspace')
    delete_strategy = ActionStrategy.DELETE_FORCE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'data_integration_client'
    extend_method_name = 'update_workspace'
    extend_identifier_param = 'workspace_id'
    extend_details_param = 'update_workspace_details'
    extend_details_cls = UpdateWorkspaceDetails

    def force_delete(self, deleter, resource) -> Result:
        region = self._region(deleter, resource)
        if not region:
            return Result(
                HTTPStatus.BAD_REQUEST,
                message=f"Region missing for {self.resource_type} {resource.get('identifier')}",
                metadata={
                    "method": "force",
                    "resource_type": self.resource_type,
                    "identifier": resource.get("identifier"),
                },
            )
        response = deleter.clients[region].data_integration_client.delete_workspace(
            workspace_id=resource["identifier"],
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
            },
        )
