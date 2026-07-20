#!/usr/bin/python3.11
from oci.core.models import UpdateDrgDetails

from .base import ActionStrategy, BaseResourceType


class DrgResource(BaseResourceType):
    resource_type = 'Drg'
    aliases = ('drg', 'DRG')
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'virtual_network_client'
    delete_method_name = 'change_drg_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'virtual_network_client'
    extend_method_name = 'update_drg'
    extend_identifier_param = 'drg_id'
    extend_details_param = 'update_drg_details'
    extend_details_cls = UpdateDrgDetails
