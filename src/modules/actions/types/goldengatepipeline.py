#!/usr/bin/python3.11
from oci.golden_gate.models import UpdatePipelineDetails

from .base import ActionStrategy, BaseResourceType


class GoldenGatePipelineResource(BaseResourceType):
    resource_type = 'GoldenGatePipeline'
    aliases = ('goldengatepipeline', 'golden_gate_pipeline')
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'golden_gate_client'
    delete_method_name = 'change_pipeline_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'golden_gate_client'
    extend_method_name = 'update_pipeline'
    extend_identifier_param = 'pipeline_id'
    extend_details_param = 'update_pipeline_details'
    extend_details_cls = UpdatePipelineDetails
