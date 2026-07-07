#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class CpeResource(ResourceType):
    resource_type = 'Cpe'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
