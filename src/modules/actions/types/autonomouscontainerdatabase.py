#!/usr/bin/python3.11
from oci.database.models import UpdateAutonomousContainerDatabaseDetails

from .base import ActionStrategy, BaseResourceType


class AutonomousContainerDatabaseResource(BaseResourceType):
    resource_type = 'AutonomousContainerDatabase'
    aliases = ('autonomouscontainerdatabase',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'database_client'
    extend_method_name = 'update_autonomous_container_database'
    extend_identifier_param = 'autonomous_container_database_id'
    extend_details_param = 'update_autonomous_container_database_details'
    extend_details_cls = UpdateAutonomousContainerDatabaseDetails
