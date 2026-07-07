#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class FileSystemResource(ResourceType):
    resource_type = 'FileSystem'
    aliases = ('filesystem',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
