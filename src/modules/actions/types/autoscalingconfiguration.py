#!/usr/bin/python3.11
from oci.autoscaling.models import UpdateAutoScalingConfigurationDetails

from .base import ActionStrategy, BaseResourceType


class AutoScalingConfigurationResource(BaseResourceType):
    resource_type = 'AutoScalingConfiguration'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'autoscaling_client'
    extend_method_name = 'update_auto_scaling_configuration'
    extend_identifier_param = 'auto_scaling_configuration_id'
    extend_details_param = 'update_auto_scaling_configuration_details'
    extend_details_cls = UpdateAutoScalingConfigurationDetails
