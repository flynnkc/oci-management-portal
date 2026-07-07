#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class MountTargetResource(ResourceType):
    resource_type = 'MountTarget'
    aliases = ('mounttarget',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
