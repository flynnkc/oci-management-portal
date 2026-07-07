#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class GroupResource(ResourceType):
    resource_type = 'Group'
    delete_strategy = ActionStrategy.DELETE_FORCE
    extend_strategy = ActionStrategy.EXTEND_IDENTITY
