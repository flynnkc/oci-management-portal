#!/usr/bin/python3.11
from oci.email.models import UpdateSenderDetails

from .base import ActionStrategy, BaseResourceType


class EmailSenderResource(BaseResourceType):
    resource_type = 'EmailSender'
    aliases = ('emailsender',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'email_client'
    extend_method_name = 'update_sender'
    extend_identifier_param = 'sender_id'
    extend_details_param = 'update_sender_details'
    extend_details_cls = UpdateSenderDetails
