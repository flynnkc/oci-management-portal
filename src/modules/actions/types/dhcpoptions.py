#!/usr/bin/python3.11
from oci.core.models import UpdateDhcpDetails

from .base import ActionStrategy, BaseResourceType


class DhcpOptionsResource(BaseResourceType):
    resource_type = 'DhcpOptions'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'virtual_network_client'
    extend_method_name = 'update_dhcp_options'
    extend_identifier_param = 'dhcp_id'
    extend_details_param = 'update_dhcp_details'
    extend_details_cls = UpdateDhcpDetails
