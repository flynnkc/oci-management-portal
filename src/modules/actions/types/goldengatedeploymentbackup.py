#!/usr/bin/python3.11
from oci.golden_gate.models import UpdateDeploymentBackupDetails

from .base import ActionStrategy, BaseResourceType


class GoldenGateDeploymentBackupResource(BaseResourceType):
    resource_type = 'GoldenGateDeploymentBackup'
    aliases = ('goldengatedeploymentbackup', 'golden_gate_deployment_backup')
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'golden_gate_client'
    delete_method_name = 'change_deployment_backup_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'golden_gate_client'
    extend_method_name = 'update_deployment_backup'
    extend_identifier_param = 'deployment_backup_id'
    extend_details_param = 'update_deployment_backup_details'
    extend_details_cls = UpdateDeploymentBackupDetails
