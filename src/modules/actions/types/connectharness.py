#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class ConnectHarnessResource(BaseResourceType):
    resource_type = 'ConnectHarness'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
