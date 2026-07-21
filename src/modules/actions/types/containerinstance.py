#!/usr/bin/python3.11
from oci.container_instances.models import UpdateContainerInstanceDetails

from .base import ActionStrategy, BaseResourceType


class ContainerInstanceResource(BaseResourceType):
    resource_type = 'ContainerInstance'
    aliases = ('containerinstance', 'container_instance')
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'container_instance_client'
    delete_method_name = 'change_container_instance_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'container_instance_client'
    extend_method_name = 'update_container_instance'
    extend_identifier_param = 'container_instance_id'
    extend_details_param = 'update_container_instance_details'
    extend_details_cls = UpdateContainerInstanceDetails
