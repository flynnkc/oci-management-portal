#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class DataScienceNotebookSessionResource(ResourceType):
    resource_type = 'DataScienceNotebookSession'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
