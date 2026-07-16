#!/usr/bin/python3.11
from oci.core.models import UpdateCpeDetails

from .base import ActionStrategy, BaseResourceType


class CpeResource(BaseResourceType):
    resource_type = 'Cpe'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'virtual_network_client'
    extend_method_name = 'update_cpe'
    extend_identifier_param = 'cpe_id'
    extend_details_param = 'update_cpe_details'
    extend_details_cls = UpdateCpeDetails
