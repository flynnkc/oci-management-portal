#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class FileSystemResource(BaseResourceType):
    resource_type = 'FileSystem'
    aliases = ('filesystem',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
