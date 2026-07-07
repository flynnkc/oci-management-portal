#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class LocalPeeringGatewayResource(ResourceType):
    resource_type = 'LocalPeeringGateway'
    aliases = ('localpeeringgateway',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
