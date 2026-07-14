#!/usr/bin/python3.11
from oci.file_storage.models import UpdateFileSystemDetails

from .base import ActionStrategy, BaseResourceType


class FileSystemResource(BaseResourceType):
    resource_type = 'FileSystem'
    aliases = ('filesystem',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'file_storage_client'
    extend_method_name = 'update_file_system'
    extend_identifier_param = 'file_system_id'
    extend_details_param = 'update_file_system_details'
    extend_details_cls = UpdateFileSystemDetails
