#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class VolumeGroupResource(BaseResourceType):
    resource_type = 'VolumeGroup'
    aliases = ('volumegroup',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
