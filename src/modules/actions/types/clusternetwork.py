#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class ClusterNetworkResource(BaseResourceType):
    resource_type = 'ClusterNetwork'
    aliases = ('clusternetwork',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
