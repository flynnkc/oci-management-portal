#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class WaasPolicyResource(ResourceType):
    resource_type = 'WaasPolicy'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
