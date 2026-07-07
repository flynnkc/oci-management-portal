#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class NoSQLTableResource(ResourceType):
    resource_type = 'NoSQLTable'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
