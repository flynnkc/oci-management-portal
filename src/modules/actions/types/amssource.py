#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class AmsSourceResource(ResourceType):
    resource_type = 'AmsSource'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
