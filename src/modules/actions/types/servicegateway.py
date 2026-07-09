#!/usr/bin/python3.11
from oci.core.models import UpdateServiceGatewayDetails

from .base import ActionStrategy, BaseResourceType


class ServiceGatewayResource(BaseResourceType):
    resource_type = 'ServiceGateway'
    aliases = ('servicegateway',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'virtual_network_client'
    extend_method_name = 'update_service_gateway'
    extend_identifier_param = 'service_gateway_id'
    extend_details_param = 'update_service_gateway_details'
    extend_details_cls = UpdateServiceGatewayDetails
