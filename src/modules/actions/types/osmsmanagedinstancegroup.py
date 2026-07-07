#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class OsmsManagedInstanceGroupResource(ResourceType):
    resource_type = 'OsmsManagedInstanceGroup'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
