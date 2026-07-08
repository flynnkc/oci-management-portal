#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class AutonomousExadataInfrastructureResource(BaseResourceType):
    resource_type = 'AutonomousExadataInfrastructure'
    aliases = ('autonomousexadatainfrastructure',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
