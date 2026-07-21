#!/usr/bin/python3.11
from oci.golden_gate.models import UpdateDatabaseRegistrationDetails

from .base import ActionStrategy, BaseResourceType


class GoldenGateDatabaseRegistrationResource(BaseResourceType):
    resource_type = 'GoldenGateDatabaseRegistration'
    aliases = ('goldengatedatabaseregistration', 'golden_gate_database_registration')
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'golden_gate_client'
    delete_method_name = 'change_database_registration_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'golden_gate_client'
    extend_method_name = 'update_database_registration'
    extend_identifier_param = 'database_registration_id'
    extend_details_param = 'update_database_registration_details'
    extend_details_cls = UpdateDatabaseRegistrationDetails
