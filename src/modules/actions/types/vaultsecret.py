#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class VaultSecretResource(BaseResourceType):
    resource_type = 'VaultSecret'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
