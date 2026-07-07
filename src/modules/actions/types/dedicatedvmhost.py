#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class DedicatedVmHostResource(ResourceType):
    resource_type = 'DedicatedVmHost'
    aliases = ('dedicatedvmhost',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
