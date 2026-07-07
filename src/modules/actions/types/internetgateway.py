#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class InternetGatewayResource(ResourceType):
    resource_type = 'InternetGateway'
    aliases = ('internetgateway',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
