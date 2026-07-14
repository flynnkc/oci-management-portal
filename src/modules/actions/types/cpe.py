#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class CpeResource(BaseResourceType):
    resource_type = 'Cpe'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
