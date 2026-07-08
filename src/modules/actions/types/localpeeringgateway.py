#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class LocalPeeringGatewayResource(BaseResourceType):
    resource_type = 'LocalPeeringGateway'
    aliases = ('localpeeringgateway',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
