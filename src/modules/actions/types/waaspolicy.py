#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class WaasPolicyResource(BaseResourceType):
    resource_type = 'WaasPolicy'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
