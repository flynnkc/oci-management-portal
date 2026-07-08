#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class BucketResource(BaseResourceType):
    resource_type = 'Bucket'
    aliases = ('bucket',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
