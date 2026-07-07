#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class IntegrationInstanceResource(ResourceType):
    resource_type = 'IntegrationInstance'
    aliases = ('integrationinstance',)
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'integration_client'
    delete_method_name = 'change_integration_instance_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
