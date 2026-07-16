#!/usr/bin/python3.11
from oci.email.models import UpdateEmailDomainDetails

from .base import ActionStrategy, BaseResourceType


class EmaildomainResource(BaseResourceType):
    resource_type = 'EmailDomain'
    aliases = ('emaildomain',)
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'email_client'
    delete_method_name = 'change_email_domain_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'email_client'
    extend_method_name = 'update_email_domain'
    extend_identifier_param = 'email_domain_id'
    extend_details_param = 'update_email_domain_details'
    extend_details_cls = UpdateEmailDomainDetails
