#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class ApiDeploymentResource(ResourceType):
    resource_type = 'ApiDeployment'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
