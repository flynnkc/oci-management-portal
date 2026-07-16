#!/usr/bin/python3.11
from oci.streaming.models import UpdateConnectHarnessDetails

from .base import ActionStrategy, BaseResourceType


class ConnectHarnessResource(BaseResourceType):
    resource_type = 'ConnectHarness'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'stream_admin_client'
    extend_method_name = 'update_connect_harness'
    extend_identifier_param = 'connect_harness_id'
    extend_details_param = 'update_connect_harness_details'
    extend_details_cls = UpdateConnectHarnessDetails
