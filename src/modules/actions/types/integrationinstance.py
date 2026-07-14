#!/usr/bin/python3.11
from oci.integration.models import UpdateIntegrationInstanceDetails

from .base import ActionStrategy, BaseResourceType


class IntegrationInstanceResource(BaseResourceType):
    resource_type = 'IntegrationInstance'
    aliases = ('integrationinstance',)
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'integration_client'
    delete_method_name = 'change_integration_instance_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'integration_client'
    extend_method_name = 'update_integration_instance'
    extend_identifier_param = 'integration_instance_id'
    extend_details_param = 'update_integration_instance_details'
    extend_details_cls = UpdateIntegrationInstanceDetails
