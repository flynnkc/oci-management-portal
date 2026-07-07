#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class VolumeGroupResource(ResourceType):
    resource_type = 'VolumeGroup'
    aliases = ('volumegroup',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
