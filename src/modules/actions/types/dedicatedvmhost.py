#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class DedicatedVmHostResource(BaseResourceType):
    resource_type = 'DedicatedVmHost'
    aliases = ('dedicatedvmhost',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
