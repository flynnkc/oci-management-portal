#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class InstancePoolResource(BaseResourceType):
    resource_type = 'InstancePool'
    aliases = ('instancepool',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
