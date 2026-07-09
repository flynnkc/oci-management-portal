#!/usr/bin/python3.11
from oci.database.models import UpdateAutonomousExadataInfrastructureDetails

from .base import ActionStrategy, BaseResourceType


class AutonomousExadataInfrastructureResource(BaseResourceType):
    resource_type = 'AutonomousExadataInfrastructure'
    aliases = ('autonomousexadatainfrastructure',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'database_client'
    extend_method_name = 'update_autonomous_exadata_infrastructure'
    extend_identifier_param = 'autonomous_exadata_infrastructure_id'
    extend_details_param = 'update_autonomous_exadata_infrastructure_details'
    extend_details_cls = UpdateAutonomousExadataInfrastructureDetails
