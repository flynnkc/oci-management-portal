#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class NetworkSecurityGroupResource(BaseResourceType):
    resource_type = 'NetworkSecurityGroup'
    aliases = ('networksecuritygroup',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
