#!/usr/bin/python3.11
from oci.network_load_balancer.models import UpdateNetworkLoadBalancerDetails

from .base import ActionStrategy, BaseResourceType


class NetworkLoadBalancerResource(BaseResourceType):
    resource_type = 'NetworkLoadBalancer'
    aliases = ('networkloadbalancer', 'network_load_balancer')
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'network_load_balancer_client'
    delete_method_name = 'change_network_load_balancer_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'network_load_balancer_client'
    extend_method_name = 'update_network_load_balancer'
    extend_identifier_param = 'network_load_balancer_id'
    extend_details_param = 'update_network_load_balancer_details'
    extend_details_cls = UpdateNetworkLoadBalancerDetails
