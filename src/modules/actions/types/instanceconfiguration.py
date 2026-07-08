#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class InstanceConfigurationResource(BaseResourceType):
    resource_type = 'InstanceConfiguration'
    aliases = ('instanceconfiguration',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
