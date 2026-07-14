#!/usr/bin/python3.11
from oci.core.models import UpdateNetworkSecurityGroupDetails

from .base import ActionStrategy, BaseResourceType


class NetworkSecurityGroupResource(BaseResourceType):
    resource_type = 'NetworkSecurityGroup'
    aliases = ('networksecuritygroup',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'virtual_network_client'
    extend_method_name = 'update_network_security_group'
    extend_identifier_param = 'network_security_group_id'
    extend_details_param = 'update_network_security_group_details'
    extend_details_cls = UpdateNetworkSecurityGroupDetails
