#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class DataSafePrivateEndpointResource(BaseResourceType):
    resource_type = 'DataSafePrivateEndpoint'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
