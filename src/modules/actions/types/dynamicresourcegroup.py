#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class DynamicResourceGroupResource(ResourceType):
    resource_type = 'DynamicResourceGroup'
    delete_strategy = ActionStrategy.DELETE_FORCE
    extend_strategy = ActionStrategy.EXTEND_IDENTITY
