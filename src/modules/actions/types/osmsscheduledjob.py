#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class OsmsScheduledJobResource(BaseResourceType):
    resource_type = 'OsmsScheduledJob'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
