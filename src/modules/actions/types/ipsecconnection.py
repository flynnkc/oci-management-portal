#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class IPSecConnectionResource(ResourceType):
    resource_type = 'IPSecConnection'
    aliases = ('ipsecconnection',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
