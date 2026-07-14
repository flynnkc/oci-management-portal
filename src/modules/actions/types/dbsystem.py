#!/usr/bin/python3.11
from oci.database.models import UpdateDbSystemDetails

from .base import ActionStrategy, BaseResourceType


class DbSystemResource(BaseResourceType):
    resource_type = 'DbSystem'
    aliases = ('dbsystem',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'database_client'
    extend_method_name = 'update_db_system'
    extend_identifier_param = 'db_system_id'
    extend_details_param = 'update_db_system_details'
    extend_details_cls = UpdateDbSystemDetails
