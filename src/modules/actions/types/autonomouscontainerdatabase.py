#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class AutonomousContainerDatabaseResource(ResourceType):
    resource_type = 'AutonomousContainerDatabase'
    aliases = ('autonomouscontainerdatabase',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
