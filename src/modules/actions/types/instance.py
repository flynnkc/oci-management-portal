#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class InstanceResource(BaseResourceType):
    # Most resource plugins only declare the supported strategies. The shared
    # BaseResourceType handlers implement the common bulk delete and bulk extend
    # paths selected here.
    resource_type = 'Instance'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_BULK_TAG
