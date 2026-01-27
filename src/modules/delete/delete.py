#!/usr/bin/python3.11

import logging
from http import HTTPStatus
from typing import List, Dict

from oci import Signer
from oci.identity.models import BulkMoveResourcesDetails
from oci.exceptions import ServiceError

from .client_bundle import ClientBundle
from ..utils import log_factory


class Deleter:
    """
    Bulk supported:
      - Try Bulk
      - If it works, stop
      - If it fails, log and try SDK

    Non bulk:
      - Skip Bulk
      - Try SDK

    If both fail:
      - Log OCID for UI
    """

    # OCI bulk supported entity types
    BULK_SUPPORTED_TYPES = {
        "AnalyticsInstance", "ApiDeployment", "ApiGateway", "AmsMigration", "AmsSource",
        "AutoScalingConfiguration", "BootVolume", "BootVolumeBackup", "Volume", "VolumeBackup",
        "VolumeGroup", "VolumeGroupBackup", "Cpe", "CrossConnect", "CrossConnectGroup",
        "IPSecConnection", "RemotePeeringConnection", "VirtualCircuit", "ClusterNetwork",
        "DedicatedVmHost", "Image", "Instance", "InstanceConfiguration", "InstancePool",
        "DataCatalog", "DataSafePrivateEndpoint", "DataScienceModel",
        "DataScienceNotebookSession", "DataScienceProject",
        "AutonomousContainerDatabase", "AutonomousDatabase",
        "AutonomousExadataInfrastructure", "BackupDestination", "DbSystem",
        "ExadataInfrastructure", "VmCluster", "EmailSender", "EventRule",
        "FileSystem", "MountTarget", "FunctionsApplication", "Key", "Vault",
        "LoadBalancer", "Alarm", "NatGateway", "NoSQLTable", "OnsSubscription",
        "OnsTopic", "Bucket", "OceInstance", "OdaInstance",
        "OsmsManagedInstanceGroup", "OsmsScheduledJob", "OsmsSoftwareSource",
        "OrmStack", "ConnectHarness", "Stream", "TagNamespace", "VaultSecret",
        "DhcpOptions", "InternetGateway", "LocalPeeringGateway",
        "NetworkSecurityGroup", "PublicIp", "RouteTable", "SecurityList",
        "ServiceGateway", "Subnet", "Vcn", "WaasCertificate", "WaasPolicy",
    }

    def __init__(self, config: dict[str, str], quarantine_cmp: str,
                 signer: Signer | None=None,
                 handler: logging.Handler=logging.StreamHandler(),
                 log_level: int | str=logging.INFO, regions=None):
        self.logger = log_factory(__name__, log_level, handler)
        self.config = config
        self.signer = signer
        self.quarantine_cmp = quarantine_cmp
        self.clients = self.create_clients(regions)

        # SDK-only movers
        self.move_tree = {
            "LogGroup": self.move_log_group,
            "DevOpsProject": self.move_devops_project,
            "DevOpsBuildPipeline": self.move_devops_build_pipeline,
            "DevOpsDeployPipeline": self.move_devops_deploy_pipeline,
            "DevOpsRepository": self.move_devops_repository,
            "IntegrationInstance": self.move_integration_instance,
            "Bastion": self.move_bastion,
        }

        self.logger.info("Deleter initialized")

    # -------------------------
    # Client creation
    # -------------------------
    def create_clients(self, regions):
        clients = {}
        if not regions:
            clients[self.config["region"]] = ClientBundle(self.config, self.signer)
        else:
            for r in regions:
                self.config["region"] = r
                self.signer.region = r
                clients[r] = ClientBundle(self.config, self.signer)
        return clients

    # -------------------------
    # Entry point
    # -------------------------
    def move(self, resources: List[Dict], **kwargs):
        region = kwargs.get("region")
        target = kwargs.get("target_compartment_id", self.quarantine_cmp)

        for r in resources:
            self._move_single(r, region, target)

        return HTTPStatus.OK

    # -------------------------
    # Specific resource type logic
    # -------------------------
    def _move_single(self, resource, region, target):
        rtype = resource.get("resource_type")
        ocid = resource.get("identifier")

        # Bulk path
        if rtype in Deleter.BULK_SUPPORTED_TYPES:
            if self._try_bulk_one(resource, region, target):
                self.logger.info("Bulk move succeeded for %s (%s)", rtype, ocid)
                return
            else:
                self.logger.error("Bulk supported resource failed via bulk: %s (%s)", rtype, ocid)

        # SDK fallback
        func = self.move_tree.get(rtype)
        if func:
            try:
                func(identifier=ocid, region=region, target_compartment_id=target, **resource)
                self.logger.info("SDK move succeeded for %s (%s)", rtype, ocid)
                return
            except Exception:
                self.logger.exception("SDK move failed for %s (%s)", rtype, ocid)

        # Final failure
        self.logger.error("No move implementation for %s (%s)", rtype, ocid)

    # -------------------------
    # Bulk Logic
    # -------------------------
    def _try_bulk_one(self, resource, region, target):
        try:
            rtype = resource["resource_type"]
            ocid = resource["identifier"]

            bulk_resource = {
                "entityType": rtype,
                "identifier": ocid
            }

            # Buckets need metadata
            if rtype == "Bucket":
                namespace = (
                    resource.get("namespace")
                    or resource.get("namespace_name")
                    or self.clients[region].object_storage_client.get_namespace().data
                )

                bucket_name = (
                    resource.get("identifier_name")
                    or resource.get("display_name")
                    or resource.get("bucket_name")
                )

                if not bucket_name:
                    self.logger.error("Bucket name missing for %s", ocid)
                    return False

                bulk_resource["metadata"] = {
                    "namespaceName": namespace,
                    "bucketName": bucket_name
                }

                self.logger.info(
                    "Bulk bucket payload → ocid=%s name=%s namespace=%s",
                    ocid, bucket_name, namespace
                )

            details = BulkMoveResourcesDetails(
                target_compartment_id=target,
                resources=[bulk_resource],
            )

            self.clients[region].identity_client.bulk_move_resources(
                resource["compartment_id"], details
            )

            return True

        except ServiceError as e:
            self.logger.info(
                "Bulk move rejected by OCI for %s (%s): %s",
                rtype,
                ocid,
                e.message,
            )
            return False

        except Exception:
            self.logger.exception("Bulk move crashed for %s", ocid)
            return False

    # -------------------------
    # Specific SDK implementations
    # -------------------------
    def move_log_group(self, identifier, region, target_compartment_id, **_):
        self.clients[region].logging_management_client.change_log_group_compartment(
            identifier, {"compartmentId": target_compartment_id}
        )

    def move_devops_project(self, identifier, region, target_compartment_id, **_):
        self.clients[region].devops_client.change_project_compartment(
            identifier, {"compartmentId": target_compartment_id}
        )

    def move_devops_build_pipeline(self, identifier, region, target_compartment_id, **_):
        self.clients[region].devops_client.change_build_pipeline_compartment(
            identifier, {"compartmentId": target_compartment_id}
        )

    def move_devops_deploy_pipeline(self, identifier, region, target_compartment_id, **_):
        self.clients[region].devops_client.change_deploy_pipeline_compartment(
            identifier, {"compartmentId": target_compartment_id}
        )

    def move_devops_repository(self, identifier, region, target_compartment_id, **_):
        self.clients[region].devops_client.change_repository_compartment(
            identifier, {"compartmentId": target_compartment_id}
        )

    def move_integration_instance(self, identifier, region, target_compartment_id, **_):
        self.clients[region].integration_client.change_integration_instance_compartment(
            identifier, {"compartmentId": target_compartment_id}
        )

    def move_bastion(self, identifier, region, target_compartment_id, **_):
        self.clients[region].bastion_client.change_bastion_compartment(
            identifier, {"compartmentId": target_compartment_id}
        )