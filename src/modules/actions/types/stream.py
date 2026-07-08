#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class StreamResource(BaseResourceType):
    resource_type = 'Stream'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_BULK_TAG
