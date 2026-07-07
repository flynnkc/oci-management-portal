#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class OnsTopicResource(ResourceType):
    resource_type = 'OnsTopic'
    aliases = ('onstopic',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
