#!/usr/bin/python3.11
from oci.events.models import UpdateRuleDetails

from .base import ActionStrategy, BaseResourceType


class EventRuleResource(BaseResourceType):
    resource_type = 'EventRule'
    aliases = ('eventrule',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'events_client'
    extend_method_name = 'update_rule'
    extend_identifier_param = 'rule_id'
    extend_details_param = 'update_rule_details'
    extend_details_cls = UpdateRuleDetails
