#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class LogGroupResource(ResourceType):
    # SDK-move resources declare the OCI client and method used by the generic
    # delete handler. Extend support uses the Extender SDK tag update map.
    resource_type = 'LogGroup'
    aliases = ('loggroup',)
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'logging_management_client'
    delete_method_name = 'change_log_group_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
