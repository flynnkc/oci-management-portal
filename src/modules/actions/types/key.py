#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class KeyResource(BaseResourceType):
    resource_type = 'Key'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_BULK_TAG
