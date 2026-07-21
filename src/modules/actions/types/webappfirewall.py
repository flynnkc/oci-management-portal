#!/usr/bin/python3.11
from oci.waf.models import UpdateWebAppFirewallDetails

from .base import ActionStrategy, BaseResourceType


class WebAppFirewallResource(BaseResourceType):
    resource_type = 'WebAppFirewall'
    aliases = ('webappfirewall', 'web_app_firewall')
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'waf_client'
    delete_method_name = 'change_web_app_firewall_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'waf_client'
    extend_method_name = 'update_web_app_firewall'
    extend_identifier_param = 'web_app_firewall_id'
    extend_details_param = 'update_web_app_firewall_details'
    extend_details_cls = UpdateWebAppFirewallDetails
