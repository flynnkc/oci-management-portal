#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class VolumeGroupBackupResource(BaseResourceType):
    resource_type = 'VolumeGroupBackup'
    aliases = ('volumegroupbackup',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
