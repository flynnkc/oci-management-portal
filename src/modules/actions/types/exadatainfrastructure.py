#!/usr/bin/python3.11
from oci.database.models import UpdateExadataInfrastructureDetails

from .base import ActionStrategy, BaseResourceType


class ExadataInfrastructureResource(BaseResourceType):
    resource_type = 'ExadataInfrastructure'
    aliases = ('exadatainfrastructure',)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'database_client'
    extend_method_name = 'update_exadata_infrastructure'
    extend_identifier_param = 'exadata_infrastructure_id'
    extend_details_param = 'update_exadata_infrastructure_details'
    extend_details_cls = UpdateExadataInfrastructureDetails
