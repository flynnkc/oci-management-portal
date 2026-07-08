#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class DataCatalogResource(BaseResourceType):
    resource_type = 'DataCatalog'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
