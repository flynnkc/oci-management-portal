#!/usr/bin/python3.11
from oci.core.models import UpdateInstanceConfigurationDetails

from .base import ActionStrategy, BaseResourceType


class InstanceConfigurationResource(BaseResourceType):
    resource_type = 'InstanceConfiguration'
    aliases = ('instanceconfiguration',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'compute_management_client'
    extend_method_name = 'update_instance_configuration'
    extend_identifier_param = 'instance_configuration_id'
    extend_details_param = 'update_instance_configuration_details'
    extend_details_cls = UpdateInstanceConfigurationDetails
