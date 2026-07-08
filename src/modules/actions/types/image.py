#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class ImageResource(BaseResourceType):
    resource_type = 'Image'
    aliases = ('image',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
