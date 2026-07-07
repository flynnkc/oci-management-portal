#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class OsmsScheduledJobResource(ResourceType):
    resource_type = 'OsmsScheduledJob'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
