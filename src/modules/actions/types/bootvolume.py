#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class BootVolumeResource(ResourceType):
    resource_type = 'BootVolume'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_BULK_TAG
