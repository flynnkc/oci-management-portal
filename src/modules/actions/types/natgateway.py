#!/usr/bin/python3.11
from oci.core.models import UpdateNatGatewayDetails

from .base import ActionStrategy, BaseResourceType


class NatGatewayResource(BaseResourceType):
    resource_type = 'NatGateway'
    aliases = ('natgateway',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'virtual_network_client'
    extend_method_name = 'update_nat_gateway'
    extend_identifier_param = 'nat_gateway_id'
    extend_details_param = 'update_nat_gateway_details'
    extend_details_cls = UpdateNatGatewayDetails
