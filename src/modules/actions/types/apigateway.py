#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class ApiGatewayResource(BaseResourceType):
    resource_type = 'ApiGateway'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
