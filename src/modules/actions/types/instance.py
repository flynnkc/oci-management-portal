#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class InstanceResource(ResourceType):
    # Most resource plugins only declare the supported strategies. The shared
    # ResourceType handlers implement the common bulk delete and bulk extend
    # paths selected here.
    resource_type = 'Instance'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_BULK_TAG
