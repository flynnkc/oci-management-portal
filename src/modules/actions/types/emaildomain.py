#!/usr/bin/python3.11
from oci.email.models import UpdateEmailDomainDetails

from .base import ActionStrategy, BaseResourceType


class EmaildomainResource(BaseResourceType):
    resource_type = 'emaildomain'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'email_client'
    extend_method_name = 'update_email_domain'
    extend_identifier_param = 'sender_id'
    extend_details_param = 'update_sender_details'
    extend_details_cls = UpdateEmailDomainDetails
