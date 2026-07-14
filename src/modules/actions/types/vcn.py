#!/usr/bin/python3.11
from oci.core.models import UpdateVcnDetails

from .base import ActionStrategy, BaseResourceType


class VcnResource(BaseResourceType):
    resource_type = 'Vcn'
    aliases = ('vcn',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'virtual_network_client'
    extend_method_name = 'update_vcn'
    extend_identifier_param = 'vcn_id'
    extend_details_param = 'update_vcn_details'
    extend_details_cls = UpdateVcnDetails
