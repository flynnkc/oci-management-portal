#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class CrossConnectResource(ResourceType):
    resource_type = 'CrossConnect'
    aliases = ('crossconnect',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
