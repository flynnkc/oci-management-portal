#!/usr/bin/python3.11
from http import HTTPStatus

from oci.database.models import UpdateDatabaseDetails

from .base import ActionStrategy, BaseResourceType
from ..result import Result


class DatabaseResource(BaseResourceType):
    resource_type = 'Database'
    aliases = ('database', 'databases')
    delete_strategy = ActionStrategy.DELETE_FORCE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'database_client'
    extend_method_name = 'update_database'
    extend_identifier_param = 'database_id'
    extend_details_param = 'update_database_details'
    extend_details_cls = UpdateDatabaseDetails

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
        response = deleter.clients[region].database_client.delete_database(
            database_id=resource["identifier"],
        )
        status = getattr(response, "status", HTTPStatus.OK)
        return Result(
            status=status,
            metadata={
                "method": "force",
                "resource_type": self.resource_type,
                "identifier": resource["identifier"],
                "region": region,
            },
        )
