#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class PublicIpResource(BaseResourceType):
    resource_type = 'PublicIp'
    aliases = ('publicip',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
