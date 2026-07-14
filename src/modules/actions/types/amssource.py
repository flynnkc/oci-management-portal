#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class AmsSourceResource(BaseResourceType):
    resource_type = 'AmsSource'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
