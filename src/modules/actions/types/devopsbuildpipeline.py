#!/usr/bin/python3.11
from oci.devops.models import UpdateBuildPipelineDetails

from .base import ActionStrategy, BaseResourceType


class DevOpsBuildPipelineResource(BaseResourceType):
    resource_type = 'DevOpsBuildPipeline'
    aliases = ('devopsbuildpipeline',)
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'devops_client'
    delete_method_name = 'change_build_pipeline_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'devops_client'
    extend_method_name = 'update_build_pipeline'
    extend_identifier_param = 'build_pipeline_id'
    extend_details_param = 'update_build_pipeline_details'
    extend_details_cls = UpdateBuildPipelineDetails
