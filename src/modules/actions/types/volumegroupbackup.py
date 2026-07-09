#!/usr/bin/python3.11
from oci.core.models import UpdateVolumeGroupBackupDetails

from .base import ActionStrategy, BaseResourceType


class VolumeGroupBackupResource(BaseResourceType):
    resource_type = 'VolumeGroupBackup'
    aliases = ('volumegroupbackup',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'blockstorage_client'
    extend_method_name = 'update_volume_group_backup'
    extend_identifier_param = 'volume_group_backup_id'
    extend_details_param = 'update_volume_group_backup_details'
    extend_details_cls = UpdateVolumeGroupBackupDetails
