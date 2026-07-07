#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class VmClusterResource(ResourceType):
    resource_type = 'VmCluster'
    aliases = ('vmcluster',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
