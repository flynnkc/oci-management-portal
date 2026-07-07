#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class AlarmResource(ResourceType):
    resource_type = 'Alarm'
    aliases = ('alarm',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
