#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class ApiGatewayResource(ResourceType):
    resource_type = 'ApiGateway'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
