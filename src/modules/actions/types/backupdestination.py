#!/usr/bin/python3.11
from oci.database.models import UpdateBackupDestinationDetails

from .base import ActionStrategy, BaseResourceType


class BackupDestinationResource(BaseResourceType):
    resource_type = 'BackupDestination'
    aliases = ('backupdestination',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'database_client'
    extend_method_name = 'update_backup_destination'
    extend_identifier_param = 'backup_destination_id'
    extend_details_param = 'update_backup_destination_details'
    extend_details_cls = UpdateBackupDestinationDetails
