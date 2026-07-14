#!/usr/bin/python3.11
from oci.monitoring.models import UpdateAlarmDetails

from .base import ActionStrategy, BaseResourceType


class AlarmResource(BaseResourceType):
    resource_type = 'Alarm'
    aliases = ('alarm',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'monitoring_client'
    extend_method_name = 'update_alarm'
    extend_identifier_param = 'alarm_id'
    extend_details_param = 'update_alarm_details'
    extend_details_cls = UpdateAlarmDetails
