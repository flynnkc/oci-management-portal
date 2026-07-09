#!/usr/bin/python3.11
from oci.resource_manager.models import UpdateStackDetails

from .base import ActionStrategy, BaseResourceType


class OrmStackResource(BaseResourceType):
    resource_type = 'OrmStack'
    aliases = ('ormstack',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'resource_manager_client'
    extend_method_name = 'update_stack'
    extend_identifier_param = 'stack_id'
    extend_details_param = 'update_stack_details'
    extend_details_cls = UpdateStackDetails
