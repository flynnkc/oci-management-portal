#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class VirtualCircuitResource(BaseResourceType):
    resource_type = 'VirtualCircuit'
    aliases = ('virtualcircuit',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
