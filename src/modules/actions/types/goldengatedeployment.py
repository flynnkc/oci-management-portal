#!/usr/bin/python3.11
from oci.golden_gate.models import UpdateDeploymentDetails

from .base import ActionStrategy, BaseResourceType


class GoldenGateDeploymentResource(BaseResourceType):
    resource_type = 'GoldenGateDeployment'
    aliases = ('goldengatedeployment', 'golden_gate_deployment')
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'golden_gate_client'
    delete_method_name = 'change_deployment_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'golden_gate_client'
    extend_method_name = 'update_deployment'
    extend_identifier_param = 'deployment_id'
    extend_details_param = 'update_deployment_details'
    extend_details_cls = UpdateDeploymentDetails
