#!/usr/bin/python3.11
from oci.core.models import UpdateSubnetDetails

from .base import ActionStrategy, BaseResourceType


class SubnetResource(BaseResourceType):
    resource_type = 'Subnet'
    aliases = ('subnet',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'virtual_network_client'
    extend_method_name = 'update_subnet'
    extend_identifier_param = 'subnet_id'
    extend_details_param = 'update_subnet_details'
    extend_details_cls = UpdateSubnetDetails
