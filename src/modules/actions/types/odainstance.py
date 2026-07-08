#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class OdaInstanceResource(BaseResourceType):
    resource_type = 'OdaInstance'
    aliases = ('odainstance',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
