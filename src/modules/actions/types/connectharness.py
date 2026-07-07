#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class ConnectHarnessResource(ResourceType):
    resource_type = 'ConnectHarness'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
