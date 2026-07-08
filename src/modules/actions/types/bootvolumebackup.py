#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class BootVolumeBackupResource(BaseResourceType):
    resource_type = 'BootVolumeBackup'
    aliases = ('bootvolumebackup',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
