#!/usr/bin/python3.11
from oci.core.models import UpdateIPSecConnectionDetails

from .base import ActionStrategy, BaseResourceType


class IPSecConnectionResource(BaseResourceType):
    resource_type = 'IPSecConnection'
    aliases = ('ipsecconnection',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'virtual_network_client'
    extend_method_name = 'update_ip_sec_connection'
    extend_identifier_param = 'ipsc_id'
    extend_details_param = 'update_ip_sec_connection_details'
    extend_details_cls = UpdateIPSecConnectionDetails
