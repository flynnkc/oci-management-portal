#!/usr/bin/python3.11
from oci.devops.models import UpdateProjectDetails

from .base import ActionStrategy, BaseResourceType


class DevOpsProjectResource(BaseResourceType):
    resource_type = 'DevOpsProject'
    aliases = ('devopsproject',)
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'devops_client'
    delete_method_name = 'change_project_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'devops_client'
    extend_method_name = 'update_project'
    extend_identifier_param = 'project_id'
    extend_details_param = 'update_project_details'
    extend_details_cls = UpdateProjectDetails
