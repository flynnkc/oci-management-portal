#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class AutoScalingConfigurationResource(BaseResourceType):
    resource_type = 'AutoScalingConfiguration'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
