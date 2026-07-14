#!/usr/bin/python3.11
from oci.logging.models import UpdateLogGroupDetails

from .base import ActionStrategy, BaseResourceType


class LogGroupResource(BaseResourceType):
    # SDK-move resources declare the OCI client/method used by the generic
    # delete handler and the SDK tag update metadata used by the generic
    # extend handler.
    resource_type = 'LogGroup'
    aliases = ('loggroup',)
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'logging_management_client'
    delete_method_name = 'change_log_group_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'logging_management_client'
    extend_method_name = 'update_log_group'
    extend_identifier_param = 'log_group_id'
    extend_details_param = 'update_log_group_details'
    extend_details_cls = UpdateLogGroupDetails
