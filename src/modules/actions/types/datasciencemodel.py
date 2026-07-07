#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class DataScienceModelResource(ResourceType):
    resource_type = 'DataScienceModel'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
