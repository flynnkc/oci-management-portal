#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class DataSafePrivateEndpointResource(ResourceType):
    resource_type = 'DataSafePrivateEndpoint'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
