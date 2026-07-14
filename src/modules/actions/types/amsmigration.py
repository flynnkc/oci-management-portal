#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class AmsMigrationResource(BaseResourceType):
    resource_type = 'AmsMigration'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
