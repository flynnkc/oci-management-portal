#!/usr/bin/python3.11
from oci.file_storage.models import UpdateMountTargetDetails

from .base import ActionStrategy, BaseResourceType


class MountTargetResource(BaseResourceType):
    resource_type = 'MountTarget'
    aliases = ('mounttarget',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'file_storage_client'
    extend_method_name = 'update_mount_target'
    extend_identifier_param = 'mount_target_id'
    extend_details_param = 'update_mount_target_details'
    extend_details_cls = UpdateMountTargetDetails
