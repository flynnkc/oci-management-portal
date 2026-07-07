#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class AutoScalingConfigurationResource(ResourceType):
    resource_type = 'AutoScalingConfiguration'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
