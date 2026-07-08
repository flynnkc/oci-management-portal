#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class AlarmResource(BaseResourceType):
    resource_type = 'Alarm'
    aliases = ('alarm',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
