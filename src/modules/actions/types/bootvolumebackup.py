#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class BootVolumeBackupResource(ResourceType):
    resource_type = 'BootVolumeBackup'
    aliases = ('bootvolumebackup',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
