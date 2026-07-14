#!/usr/bin/python3.11
from oci.oda.models import UpdateOdaInstanceDetails

from .base import ActionStrategy, BaseResourceType


class OdaInstanceResource(BaseResourceType):
    resource_type = 'OdaInstance'
    aliases = ('odainstance',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'oda_client'
    extend_method_name = 'update_oda_instance'
    extend_identifier_param = 'oda_instance_id'
    extend_details_param = 'update_oda_instance_details'
    extend_details_cls = UpdateOdaInstanceDetails
