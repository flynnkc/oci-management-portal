#!/usr/bin/python3.11
from oci.network_firewall.models import UpdateNetworkFirewallPolicyDetails

from .base import ActionStrategy, BaseResourceType


class NetworkFirewallPolicyResource(BaseResourceType):
    resource_type = 'NetworkFirewallPolicy'
    aliases = ('networkfirewallpolicy', 'network_firewall_policy')
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'network_firewall_client'
    delete_method_name = 'change_network_firewall_policy_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'network_firewall_client'
    extend_method_name = 'update_network_firewall_policy'
    extend_identifier_param = 'network_firewall_policy_id'
    extend_details_param = 'update_network_firewall_policy_details'
    extend_details_cls = UpdateNetworkFirewallPolicyDetails
