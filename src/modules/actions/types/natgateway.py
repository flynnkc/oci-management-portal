#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class NatGatewayResource(ResourceType):
    resource_type = 'NatGateway'
    aliases = ('natgateway',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
