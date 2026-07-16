#!/usr/bin/python3.11
from oci.apigateway.models import UpdateGatewayDetails

from .base import ActionStrategy, BaseResourceType


class ApiGatewayResource(BaseResourceType):
    resource_type = 'ApiGateway'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'gateway_client'
    extend_method_name = 'update_gateway'
    extend_identifier_param = 'gateway_id'
    extend_details_param = 'update_gateway_details'
    extend_details_cls = UpdateGatewayDetails
