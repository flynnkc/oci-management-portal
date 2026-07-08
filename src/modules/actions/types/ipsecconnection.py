#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class IPSecConnectionResource(BaseResourceType):
    resource_type = 'IPSecConnection'
    aliases = ('ipsecconnection',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
