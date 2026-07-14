#!/usr/bin/python3.11
from oci.core.models import UpdateRouteTableDetails

from .base import ActionStrategy, BaseResourceType


class RouteTableResource(BaseResourceType):
    resource_type = 'RouteTable'
    aliases = ('routetable',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'virtual_network_client'
    extend_method_name = 'update_route_table'
    extend_identifier_param = 'rt_id'
    extend_details_param = 'update_route_table_details'
    extend_details_cls = UpdateRouteTableDetails
