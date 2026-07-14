#!/usr/bin/python3.11
from oci.core.models import UpdateBootVolumeBackupDetails

from .base import ActionStrategy, BaseResourceType


class BootVolumeBackupResource(BaseResourceType):
    resource_type = 'BootVolumeBackup'
    aliases = ('bootvolumebackup',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'blockstorage_client'
    extend_method_name = 'update_boot_volume_backup'
    extend_identifier_param = 'boot_volume_backup_id'
    extend_details_param = 'update_boot_volume_backup_details'
    extend_details_cls = UpdateBootVolumeBackupDetails
