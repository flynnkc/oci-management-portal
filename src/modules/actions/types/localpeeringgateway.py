#!/usr/bin/python3.11
from oci.core.models import UpdateLocalPeeringGatewayDetails

from .base import ActionStrategy, BaseResourceType


class LocalPeeringGatewayResource(BaseResourceType):
    resource_type = 'LocalPeeringGateway'
    aliases = ('localpeeringgateway',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'virtual_network_client'
    extend_method_name = 'update_local_peering_gateway'
    extend_identifier_param = 'local_peering_gateway_id'
    extend_details_param = 'update_local_peering_gateway_details'
    extend_details_cls = UpdateLocalPeeringGatewayDetails
