#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class EventRuleResource(ResourceType):
    resource_type = 'EventRule'
    aliases = ('eventrule',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
