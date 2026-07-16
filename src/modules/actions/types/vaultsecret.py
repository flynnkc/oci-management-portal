#!/usr/bin/python3.11
from oci.vault.models import UpdateSecretDetails

from .base import ActionStrategy, BaseResourceType


class VaultSecretResource(BaseResourceType):
    resource_type = 'VaultSecret'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'vaults_client'
    extend_method_name = 'update_secret'
    extend_identifier_param = 'secret_id'
    extend_details_param = 'update_secret_details'
    extend_details_cls = UpdateSecretDetails
