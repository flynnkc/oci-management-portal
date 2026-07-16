#!/usr/bin/python3.11
from oci.oce.models import UpdateOceInstanceDetails

from .base import ActionStrategy, BaseResourceType


class OceInstanceResource(BaseResourceType):
    resource_type = 'OceInstance'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'oce_instance_client'
    extend_method_name = 'update_oce_instance'
    extend_identifier_param = 'oce_instance_id'
    extend_details_param = 'update_oce_instance_details'
    extend_details_cls = UpdateOceInstanceDetails
