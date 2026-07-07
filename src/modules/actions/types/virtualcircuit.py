#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class VirtualCircuitResource(ResourceType):
    resource_type = 'VirtualCircuit'
    aliases = ('virtualcircuit',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
