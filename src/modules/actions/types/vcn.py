#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class VcnResource(BaseResourceType):
    resource_type = 'Vcn'
    aliases = ('vcn',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
