#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class VolumeBackupResource(ResourceType):
    resource_type = 'VolumeBackup'
    aliases = ('volumebackup',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
