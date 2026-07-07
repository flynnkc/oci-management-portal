#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class OceInstanceResource(ResourceType):
    resource_type = 'OceInstance'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
