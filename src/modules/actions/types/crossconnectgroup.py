#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class CrossConnectGroupResource(ResourceType):
    resource_type = 'CrossConnectGroup'
    aliases = ('crossconnectgroup',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
