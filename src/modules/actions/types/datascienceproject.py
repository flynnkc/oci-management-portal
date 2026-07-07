#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class DataScienceProjectResource(ResourceType):
    resource_type = 'DataScienceProject'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
