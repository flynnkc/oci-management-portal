#!/usr/bin/python3.11
from oci.core.models import UpdatePublicIpDetails

from .base import ActionStrategy, BaseResourceType


class PublicIpResource(BaseResourceType):
    resource_type = 'PublicIp'
    aliases = ('publicip',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'virtual_network_client'
    extend_method_name = 'update_public_ip'
    extend_identifier_param = 'public_ip_id'
    extend_details_param = 'update_public_ip_details'
    extend_details_cls = UpdatePublicIpDetails
