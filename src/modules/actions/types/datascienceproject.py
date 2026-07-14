#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class DataScienceProjectResource(BaseResourceType):
    resource_type = 'DataScienceProject'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
