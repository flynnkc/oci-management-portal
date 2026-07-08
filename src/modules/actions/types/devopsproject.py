#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class DevOpsProjectResource(BaseResourceType):
    resource_type = 'DevOpsProject'
    aliases = ('devopsproject',)
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'devops_client'
    delete_method_name = 'change_project_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
