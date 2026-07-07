#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class DhcpOptionsResource(ResourceType):
    resource_type = 'DhcpOptions'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
