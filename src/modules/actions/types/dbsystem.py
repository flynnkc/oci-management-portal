#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class DbSystemResource(BaseResourceType):
    resource_type = 'DbSystem'
    aliases = ('dbsystem',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
