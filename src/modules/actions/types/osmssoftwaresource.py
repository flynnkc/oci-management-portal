#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class OsmsSoftwareSourceResource(ResourceType):
    resource_type = 'OsmsSoftwareSource'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
