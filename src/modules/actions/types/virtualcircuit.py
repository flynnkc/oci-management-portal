#!/usr/bin/python3.11
from oci.core.models import UpdateVirtualCircuitDetails

from .base import ActionStrategy, BaseResourceType


class VirtualCircuitResource(BaseResourceType):
    resource_type = 'VirtualCircuit'
    aliases = ('virtualcircuit',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'virtual_network_client'
    extend_method_name = 'update_virtual_circuit'
    extend_identifier_param = 'virtual_circuit_id'
    extend_details_param = 'update_virtual_circuit_details'
    extend_details_cls = UpdateVirtualCircuitDetails
