#!/usr/bin/python3.11
from oci.golden_gate.models import UpdateConnectionDetails

from .base import ActionStrategy, BaseResourceType


class GoldenGateConnectionResource(BaseResourceType):
    resource_type = 'GoldenGateConnection'
    aliases = ('goldengateconnection', 'golden_gate_connection')
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'golden_gate_client'
    delete_method_name = 'change_connection_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'golden_gate_client'
    extend_method_name = 'update_connection'
    extend_identifier_param = 'connection_id'
    extend_details_param = 'update_connection_details'
    extend_details_cls = UpdateConnectionDetails
