#!/usr/bin/python3.11
from oci.core.models import UpdateRemotePeeringConnectionDetails

from .base import ActionStrategy, BaseResourceType


class RemotePeeringConnectionResource(BaseResourceType):
    resource_type = 'RemotePeeringConnection'
    aliases = ('remotepeeringconnection',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'virtual_network_client'
    extend_method_name = 'update_remote_peering_connection'
    extend_identifier_param = 'remote_peering_connection_id'
    extend_details_param = 'update_remote_peering_connection_details'
    extend_details_cls = UpdateRemotePeeringConnectionDetails
