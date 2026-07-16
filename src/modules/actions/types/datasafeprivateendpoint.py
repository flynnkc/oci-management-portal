#!/usr/bin/python3.11
from oci.data_safe.models import UpdateDataSafePrivateEndpointDetails
from .base import ActionStrategy, BaseResourceType


class DataSafePrivateEndpointResource(BaseResourceType):
    resource_type = 'DataSafePrivateEndpoint'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'data_safe_client'
    extend_method_name = 'update_data_safe_private_endpoint'
    extend_identifier_param = 'data_safe_private_endpoint_id'
    extend_details_param = 'update_data_safe_private_endpoint_details'
    extend_details_cls = UpdateDataSafePrivateEndpointDetails
