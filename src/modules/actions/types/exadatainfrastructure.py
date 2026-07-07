#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class ExadataInfrastructureResource(ResourceType):
    resource_type = 'ExadataInfrastructure'
    aliases = ('exadatainfrastructure',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
