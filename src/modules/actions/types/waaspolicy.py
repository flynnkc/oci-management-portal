#!/usr/bin/python3.11
from oci.waas.models import UpdateWaasPolicyDetails

from .base import ActionStrategy, BaseResourceType


class WaasPolicyResource(BaseResourceType):
    resource_type = 'WaasPolicy'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'waas_client'
    extend_method_name = 'update_waas_policy'
    extend_identifier_param = 'waas_policy_id'
    extend_details_param = 'update_waas_policy_details'
    extend_details_cls = UpdateWaasPolicyDetails
