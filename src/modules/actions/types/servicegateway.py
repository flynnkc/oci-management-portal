#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class ServiceGatewayResource(BaseResourceType):
    resource_type = 'ServiceGateway'
    aliases = ('servicegateway',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
