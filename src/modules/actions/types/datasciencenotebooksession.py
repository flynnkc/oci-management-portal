#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class DataScienceNotebookSessionResource(BaseResourceType):
    resource_type = 'DataScienceNotebookSession'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
