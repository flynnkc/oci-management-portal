#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class OceInstanceResource(BaseResourceType):
    resource_type = 'OceInstance'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
