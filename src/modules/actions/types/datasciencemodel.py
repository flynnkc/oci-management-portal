#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class DataScienceModelResource(BaseResourceType):
    resource_type = 'DataScienceModel'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
