#!/usr/bin/python3.11
from oci.bastion.models import UpdateBastionDetails

from .base import ActionStrategy, BaseResourceType


class BastionResource(BaseResourceType):
    resource_type = 'Bastion'
    aliases = ('bastion',)
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'bastion_client'
    delete_method_name = 'change_bastion_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'bastion_client'
    extend_method_name = 'update_bastion'
    extend_identifier_param = 'bastion_id'
    extend_details_param = 'update_bastion_details'
    extend_details_cls = UpdateBastionDetails
