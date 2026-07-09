#!/usr/bin/python3.11
from oci.core.models import UpdateClusterNetworkDetails

from .base import ActionStrategy, BaseResourceType


class ClusterNetworkResource(BaseResourceType):
    resource_type = 'ClusterNetwork'
    aliases = ('clusternetwork',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'compute_client'
    extend_method_name = 'update_cluster_network'
    extend_identifier_param = 'cluster_network_id'
    extend_details_param = 'update_cluster_network_details'
    extend_details_cls = UpdateClusterNetworkDetails
