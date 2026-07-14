#!/usr/bin/python3.11
from oci.core.models import UpdateVolumeBackupDetails

from .base import ActionStrategy, BaseResourceType


class VolumeBackupResource(BaseResourceType):
    resource_type = 'VolumeBackup'
    aliases = ('volumebackup',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'blockstorage_client'
    extend_method_name = 'update_volume_backup'
    extend_identifier_param = 'volume_backup_id'
    extend_details_param = 'update_volume_backup_details'
    extend_details_cls = UpdateVolumeBackupDetails
