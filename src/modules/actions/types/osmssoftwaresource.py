#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class OsmsSoftwareSourceResource(BaseResourceType):
    resource_type = 'OsmsSoftwareSource'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
