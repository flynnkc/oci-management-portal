#!/usr/bin/python3.11
from oci.apigateway.models import UpdateDeploymentDetails

from .base import ActionStrategy, BaseResourceType


class ApiDeploymentResource(BaseResourceType):
    resource_type = 'ApiDeployment'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'api_deployment_client'
    extend_method_name = 'update_deployment'
    extend_identifier_param = 'deployment_id'
    extend_details_param = 'update_deployment_details'
    extend_details_cls = UpdateDeploymentDetails
