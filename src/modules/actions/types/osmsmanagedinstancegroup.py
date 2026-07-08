#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class OsmsManagedInstanceGroupResource(BaseResourceType):
    resource_type = 'OsmsManagedInstanceGroup'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
