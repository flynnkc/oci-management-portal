#!/usr/bin/python3.11
from oci.sch.models import UpdateServiceConnectorDetails

from .base import ActionStrategy, BaseResourceType


class ServiceConnectorResource(BaseResourceType):
    resource_type = 'ServiceConnector'
    aliases = ('serviceconnector', 'service_connector')
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'service_connector_client'
    delete_method_name = 'change_service_connector_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'service_connector_client'
    extend_method_name = 'update_service_connector'
    extend_identifier_param = 'service_connector_id'
    extend_details_param = 'update_service_connector_details'
    extend_details_cls = UpdateServiceConnectorDetails
