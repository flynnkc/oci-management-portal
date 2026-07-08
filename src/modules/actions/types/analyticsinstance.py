#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class AnalyticsInstanceResource(BaseResourceType):
    resource_type = 'AnalyticsInstance'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_BULK_TAG
