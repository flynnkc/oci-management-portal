#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class OrmStackResource(ResourceType):
    resource_type = 'OrmStack'
    aliases = ('ormstack',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
