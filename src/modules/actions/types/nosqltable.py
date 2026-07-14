#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class NoSQLTableResource(BaseResourceType):
    resource_type = 'NoSQLTable'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
