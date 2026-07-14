#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class VaultResource(BaseResourceType):
    resource_type = 'Vault'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_BULK_TAG
