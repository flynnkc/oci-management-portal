#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class BastionResource(ResourceType):
    resource_type = 'Bastion'
    aliases = ('bastion',)
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'bastion_client'
    delete_method_name = 'change_bastion_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
