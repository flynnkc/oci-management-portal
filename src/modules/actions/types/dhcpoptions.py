#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class DhcpOptionsResource(BaseResourceType):
    resource_type = 'DhcpOptions'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
