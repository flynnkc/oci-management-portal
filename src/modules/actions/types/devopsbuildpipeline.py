#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class DevOpsBuildPipelineResource(ResourceType):
    resource_type = 'DevOpsBuildPipeline'
    aliases = ('devopsbuildpipeline',)
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'devops_client'
    delete_method_name = 'change_build_pipeline_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
