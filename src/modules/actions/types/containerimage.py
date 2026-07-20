#!/usr/bin/python3.11
from http import HTTPStatus

from oci.artifacts.models import UpdateContainerImageDetails

from .base import ActionStrategy, BaseResourceType
from ..result import Result


class ContainerImageResource(BaseResourceType):
    resource_type = 'ContainerImage'
    aliases = ('containerimage', 'container_image')
    delete_strategy = ActionStrategy.DELETE_FORCE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'artifacts_client'
    extend_method_name = 'update_container_image'
    extend_identifier_param = 'image_id'
    extend_details_param = 'update_container_image_details'
    extend_details_cls = UpdateContainerImageDetails

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
        response = deleter.clients[region].artifacts_client.delete_container_image(
            image_id=resource["identifier"],
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
