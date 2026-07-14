#!/usr/bin/python3.11
from oci.core.models import UpdateImageDetails

from .base import ActionStrategy, BaseResourceType


class ImageResource(BaseResourceType):
    resource_type = 'Image'
    aliases = ('image',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'compute_client'
    extend_method_name = 'update_image'
    extend_identifier_param = 'image_id'
    extend_details_param = 'update_image_details'
    extend_details_cls = UpdateImageDetails
