#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class AmsMigrationResource(ResourceType):
    resource_type = 'AmsMigration'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
