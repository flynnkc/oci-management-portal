#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class VolumeGroupBackupResource(ResourceType):
    resource_type = 'VolumeGroupBackup'
    aliases = ('volumegroupbackup',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
