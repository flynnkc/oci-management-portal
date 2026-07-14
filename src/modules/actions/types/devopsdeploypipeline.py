#!/usr/bin/python3.11
from oci.devops.models import UpdateDeployPipelineDetails

from .base import ActionStrategy, BaseResourceType


class DevOpsDeployPipelineResource(BaseResourceType):
    resource_type = 'DevOpsDeployPipeline'
    aliases = ('devopsdeploypipeline',)
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'devops_client'
    delete_method_name = 'change_deploy_pipeline_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'devops_client'
    extend_method_name = 'update_deploy_pipeline'
    extend_identifier_param = 'deploy_pipeline_id'
    extend_details_param = 'update_deploy_pipeline_details'
    extend_details_cls = UpdateDeployPipelineDetails
