#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class EmailSenderResource(BaseResourceType):
    resource_type = 'EmailSender'
    aliases = ('emailsender',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
