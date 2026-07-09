#!/usr/bin/python3.11
from oci.database.models import UpdateVmClusterDetails

from .base import ActionStrategy, BaseResourceType


class VmClusterResource(BaseResourceType):
    resource_type = 'VmCluster'
    aliases = ('vmcluster',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'database_client'
    extend_method_name = 'update_vm_cluster'
    extend_identifier_param = 'vm_cluster_id'
    extend_details_param = 'update_vm_cluster_details'
    extend_details_cls = UpdateVmClusterDetails
