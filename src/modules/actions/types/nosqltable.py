#!/usr/bin/python3.11
from oci.nosql.models import UpdateTableDetails

from .base import ActionStrategy, BaseResourceType


class NoSQLTableResource(BaseResourceType):
    resource_type = 'NoSQLTable'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'nosql_client'
    extend_method_name = 'update_table'
    extend_identifier_param = 'table_name_or_id'
    extend_details_param = 'update_table_details'
    extend_details_cls = UpdateTableDetails
