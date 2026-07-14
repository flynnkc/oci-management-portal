#!/usr/bin/python3.11
from oci.core.models import UpdateSecurityListDetails

from .base import ActionStrategy, BaseResourceType


class SecurityListResource(BaseResourceType):
    resource_type = 'SecurityList'
    aliases = ('securitylist',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'virtual_network_client'
    extend_method_name = 'update_security_list'
    extend_identifier_param = 'security_list_id'
    extend_details_param = 'update_security_list_details'
    extend_details_cls = UpdateSecurityListDetails
