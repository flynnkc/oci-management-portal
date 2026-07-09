#!/usr/bin/python3.11
from oci.core.models import UpdateCrossConnectGroupDetails

from .base import ActionStrategy, BaseResourceType


class CrossConnectGroupResource(BaseResourceType):
    resource_type = 'CrossConnectGroup'
    aliases = ('crossconnectgroup',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'virtual_network_client'
    extend_method_name = 'update_cross_connect_group'
    extend_identifier_param = 'cross_connect_group_id'
    extend_details_param = 'update_cross_connect_group_details'
    extend_details_cls = UpdateCrossConnectGroupDetails
