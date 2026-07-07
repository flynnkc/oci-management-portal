#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class PublicIpResource(ResourceType):
    resource_type = 'PublicIp'
    aliases = ('publicip',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
