#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class OnsSubscriptionResource(ResourceType):
    resource_type = 'OnsSubscription'
    aliases = ('onssubscription',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
