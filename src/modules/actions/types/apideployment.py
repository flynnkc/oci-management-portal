#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class ApiDeploymentResource(BaseResourceType):
    resource_type = 'ApiDeployment'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
