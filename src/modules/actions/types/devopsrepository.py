#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class DevOpsRepositoryResource(BaseResourceType):
    resource_type = 'DevOpsRepository'
    aliases = ('devopsrepository',)
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'devops_client'
    delete_method_name = 'change_repository_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
