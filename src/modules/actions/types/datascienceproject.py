#!/usr/bin/python3.11
from oci.data_science.models import UpdateProjectDetails

from .base import ActionStrategy, BaseResourceType


class DataScienceProjectResource(BaseResourceType):
    resource_type = 'DataScienceProject'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'data_science_client'
    extend_method_name = 'update_project'
    extend_identifier_param = 'project_id'
    extend_details_param = 'update_project_details'
    extend_details_cls = UpdateProjectDetails
