#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class VaultSecretResource(ResourceType):
    resource_type = 'VaultSecret'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
