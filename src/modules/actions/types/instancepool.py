#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class InstancePoolResource(ResourceType):
    resource_type = 'InstancePool'
    aliases = ('instancepool',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
