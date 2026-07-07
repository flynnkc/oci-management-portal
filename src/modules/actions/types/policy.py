#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class PolicyResource(ResourceType):
    resource_type = 'Policy'
    delete_strategy = ActionStrategy.DELETE_FORCE
    extend_strategy = ActionStrategy.EXTEND_IDENTITY
