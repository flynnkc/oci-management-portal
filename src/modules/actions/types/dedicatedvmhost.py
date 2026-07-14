#!/usr/bin/python3.11
from oci.core.models import UpdateDedicatedVmHostDetails

from .base import ActionStrategy, BaseResourceType


class DedicatedVmHostResource(BaseResourceType):
    resource_type = 'DedicatedVmHost'
    aliases = ('dedicatedvmhost',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'compute_client'
    extend_method_name = 'update_dedicated_vm_host'
    extend_identifier_param = 'dedicated_vm_host_id'
    extend_details_param = 'update_dedicated_vm_host_details'
    extend_details_cls = UpdateDedicatedVmHostDetails
