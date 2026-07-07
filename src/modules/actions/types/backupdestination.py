#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class BackupDestinationResource(ResourceType):
    resource_type = 'BackupDestination'
    aliases = ('backupdestination',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
