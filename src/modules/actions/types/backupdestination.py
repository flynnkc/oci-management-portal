#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class BackupDestinationResource(BaseResourceType):
    resource_type = 'BackupDestination'
    aliases = ('backupdestination',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
