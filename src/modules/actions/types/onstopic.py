#!/usr/bin/python3.11
from oci.ons.models import TopicAttributesDetails

from .base import ActionStrategy, BaseResourceType


class OnsTopicResource(BaseResourceType):
    resource_type = 'OnsTopic'
    aliases = ('onstopic',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'notification_control_plane_client'
    extend_method_name = 'update_topic'
    extend_identifier_param = 'topic_id'
    extend_details_param = 'topic_attributes_details'
    extend_details_cls = TopicAttributesDetails
