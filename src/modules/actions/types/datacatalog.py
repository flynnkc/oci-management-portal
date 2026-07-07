#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class DataCatalogResource(ResourceType):
    resource_type = 'DataCatalog'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
