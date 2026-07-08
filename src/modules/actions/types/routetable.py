#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class RouteTableResource(BaseResourceType):
    resource_type = 'RouteTable'
    aliases = ('routetable',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
