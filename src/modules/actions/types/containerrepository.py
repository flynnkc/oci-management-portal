#!/usr/bin/python3.11
from oci.artifacts.models import UpdateContainerRepositoryDetails

from .base import ActionStrategy, BaseResourceType


class ContainerRepositoryResource(BaseResourceType):
    resource_type = 'ContainerRepository'
    aliases = ('containerrepository', 'container_repository')
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'artifacts_client'
    delete_method_name = 'change_container_repository_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'artifacts_client'
    extend_method_name = 'update_container_repository'
    extend_identifier_param = 'repository_id'
    extend_details_param = 'update_container_repository_details'
    extend_details_cls = UpdateContainerRepositoryDetails
