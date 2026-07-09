#!/usr/bin/python3.11
from oci.core.models import UpdateInstancePoolDetails

from .base import ActionStrategy, BaseResourceType


class InstancePoolResource(BaseResourceType):
    resource_type = 'InstancePool'
    aliases = ('instancepool',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'compute_management_client'
    extend_method_name = 'update_instance_pool'
    extend_identifier_param = 'instance_pool_id'
    extend_details_param = 'update_instance_pool_details'
    extend_details_cls = UpdateInstancePoolDetails
