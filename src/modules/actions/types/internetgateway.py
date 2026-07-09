#!/usr/bin/python3.11
from oci.core.models import UpdateInternetGatewayDetails

from .base import ActionStrategy, BaseResourceType


class InternetGatewayResource(BaseResourceType):
    resource_type = 'InternetGateway'
    aliases = ('internetgateway',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'virtual_network_client'
    extend_method_name = 'update_internet_gateway'
    extend_identifier_param = 'ig_id'
    extend_details_param = 'update_internet_gateway_details'
    extend_details_cls = UpdateInternetGatewayDetails
