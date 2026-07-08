#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class AutonomousContainerDatabaseResource(BaseResourceType):
    resource_type = 'AutonomousContainerDatabase'
    aliases = ('autonomouscontainerdatabase',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
