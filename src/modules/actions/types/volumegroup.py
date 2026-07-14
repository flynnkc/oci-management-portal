#!/usr/bin/python3.11
from oci.core.models import UpdateVolumeGroupDetails

from .base import ActionStrategy, BaseResourceType


class VolumeGroupResource(BaseResourceType):
    resource_type = 'VolumeGroup'
    aliases = ('volumegroup',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'blockstorage_client'
    extend_method_name = 'update_volume_group'
    extend_identifier_param = 'volume_group_id'
    extend_details_param = 'update_volume_group_details'
    extend_details_cls = UpdateVolumeGroupDetails
