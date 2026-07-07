#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class AppResource(ResourceType):
    resource_type = 'App'
    delete_strategy = ActionStrategy.DELETE_FORCE
    extend_strategy = ActionStrategy.EXTEND_IDENTITY
