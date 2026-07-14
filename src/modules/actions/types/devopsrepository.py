#!/usr/bin/python3.11
from oci.devops.models import UpdateRepositoryDetails

from .base import ActionStrategy, BaseResourceType


class DevOpsRepositoryResource(BaseResourceType):
    resource_type = 'DevOpsRepository'
    aliases = ('devopsrepository',)
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'devops_client'
    delete_method_name = 'change_repository_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'devops_client'
    extend_method_name = 'update_repository'
    extend_identifier_param = 'repository_id'
    extend_details_param = 'update_repository_details'
    extend_details_cls = UpdateRepositoryDetails
