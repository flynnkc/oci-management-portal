#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class SecurityListResource(ResourceType):
    resource_type = 'SecurityList'
    aliases = ('securitylist',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
