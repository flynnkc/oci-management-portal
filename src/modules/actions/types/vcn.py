#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class VcnResource(ResourceType):
    resource_type = 'Vcn'
    aliases = ('vcn',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
