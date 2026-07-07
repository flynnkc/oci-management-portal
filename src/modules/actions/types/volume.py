#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class VolumeResource(ResourceType):
    resource_type = 'Volume'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_BULK_TAG
