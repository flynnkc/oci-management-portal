#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class CrossConnectResource(BaseResourceType):
    resource_type = 'CrossConnect'
    aliases = ('crossconnect',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
