#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class TagNamespaceResource(ResourceType):
    resource_type = 'TagNamespace'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_BULK_TAG
