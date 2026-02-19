#!/usr/bin/python3.11
import logging
from http import HTTPStatus
from typing import List, Dict
from oci import Signer
from oci.identity.models import BulkMoveResourcesDetails
from oci.exceptions import ServiceError
from oci.identity_domains import IdentityDomainsClient
from oci.identity_domains.models import PatchOp, Operations
from .client_bundle import ClientBundle
from ..utils import log_factory


class Deleter:

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

    def __init__(
        self,
        config: dict[str, str],
        quarantine_cmp: str,
        signer: Signer | None = None,
        handler: logging.Handler = logging.StreamHandler(),
        log_level: int | str = logging.INFO,
        regions=None,
    ):
        self.logger = log_factory(__name__, log_level, handler)
        self.config = config
        self.signer = signer
        self.quarantine_cmp = quarantine_cmp
        self.clients = self.create_clients(regions)
        self._domain_client_cache = {}
        self._home_region = None

        self.move_tree = {
            "LogGroup": self.move_log_group,
            "DevOpsProject": self.move_devops_project,
            "DevOpsBuildPipeline": self.move_devops_build_pipeline,
            "DevOpsDeployPipeline": self.move_devops_deploy_pipeline,
            "DevOpsRepository": self.move_devops_repository,
            "IntegrationInstance": self.move_integration_instance,
            "Bastion": self.move_bastion,
        }

        self.force_delete_tree = {
            "User": self.force_delete_user,
            "Group": self.force_delete_group,
            "DynamicResourceGroup": self.force_delete_dynamic_resource_group,
            "App": self.force_delete_app,
            "Policy": self.force_delete_policy,
        }

        self.logger.info("Deleter initialized")

    # -------------------------------------------------------------
    # REGION CLIENT CREATION
    # -------------------------------------------------------------

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

    # -------------------------------------------------------------
    # MOVE ENTRY
    # -------------------------------------------------------------

    def move(self, resources: List[Dict], **kwargs):
        region = kwargs.get("region")
        target = kwargs.get("target_compartment_id", self.quarantine_cmp)

        for r in resources:
            self._move_or_force_delete_single(r, region, target)

        return HTTPStatus.OK

    def _move_or_force_delete_single(self, resource, region, target):
        rtype = resource.get("resource_type")
        ocid = resource.get("identifier")

        if rtype in self.force_delete_tree:
            try:
                self.force_delete_tree[rtype](resource)
                self.logger.info("Force delete succeeded for %s (%s)", rtype, ocid)
                return
            except Exception:
                self.logger.exception("Force delete failed for %s (%s)", rtype, ocid)

        elif rtype in Deleter.BULK_SUPPORTED_TYPES:
            if self._try_bulk_one(resource, region, target):
                self.logger.info("Bulk move succeeded for %s (%s)", rtype, ocid)
                return

        func = self.move_tree.get(rtype)
        if func:
            try:
                func(identifier=ocid, region=region, target_compartment_id=target)
                self.logger.info("SDK move succeeded for %s (%s)", rtype, ocid)
                return
            except Exception:
                self.logger.exception("SDK move failed for %s (%s)", rtype, ocid)

        self.logger.error(
            "Move/force delete failed after all attempts for %s (%s)", rtype, ocid
        )

    # -------------------------------------------------------------
    # MULTI-DOMAIN RESOLUTION
    # -------------------------------------------------------------

    def _get_identity_domain_client(self, resource):

        import oci

        resource_ocid = resource["identifier"]
        rtype = resource.get("resource_type")
        resource_compartment = resource.get("compartment_id")

        if resource_ocid in self._domain_client_cache:
            return self._domain_client_cache[resource_ocid]

        identity_client = oci.identity.IdentityClient(self.config, signer=self.signer)

        domains = identity_client.list_domains(
            compartment_id=resource_compartment,
            lifecycle_state="ACTIVE"
        ).data

        original_region = self.config.get("region")
        original_signer_region = self.signer.region

        for domain in domains:

            domain_region = domain.home_region
            domain_endpoint = domain.url

            if not domain_region or not domain_endpoint:
                continue

            try:
                self.config["region"] = domain_region
                self.signer.region = domain_region

                client = IdentityDomainsClient(
                    self.config,
                    signer=self.signer,
                    service_endpoint=domain_endpoint
                )

                if rtype == "User":
                    client.get_user(user_id=resource_ocid)

                elif rtype == "Group":
                    client.get_group(group_id=resource_ocid)

                elif rtype == "DynamicResourceGroup":
                    client.get_dynamic_resource_group(
                        dynamic_resource_group_id=resource_ocid
                    )

                elif rtype == "App":
                    client.get_app(app_id=resource_ocid)

                else:
                    continue

                self._domain_client_cache[resource_ocid] = client

                self.config["region"] = original_region
                self.signer.region = original_signer_region

                return client

            except oci.exceptions.ServiceError as e:
                if e.status == 404:
                    continue
                raise

        self.config["region"] = original_region
        self.signer.region = original_signer_region

        raise Exception(f"Resource {resource_ocid} not found in any Identity Domain")

    # -------------------------------------------------------------
    # FORCE DELETE LOGIC
    # -------------------------------------------------------------

    def force_delete_user(self, resource):
        client = self._get_identity_domain_client(resource)
        user_id = resource["identifier"]

        # Remove grants first (fix Fusion delete failures)
        try:
            grants = client.list_grants(filter=f'user eq "{user_id}"').data
            for grant in grants:
                try:
                    client.delete_grant(grant_id=grant.id)
                    self.logger.info("Removed grant %s for user %s", grant.id, user_id)
                except Exception as e:
                    self.logger.warning("Grant removal failed %s: %s", grant.id, e)
        except Exception as e:
            self.logger.warning("Grant listing failed for %s: %s", user_id, e)

        client.delete_user(user_id=user_id, force_delete=True)

    def force_delete_group(self, resource):
        client = self._get_identity_domain_client(resource)
        client.delete_group(group_id=resource["identifier"], force_delete=True)

    def force_delete_dynamic_resource_group(self, resource):
        client = self._get_identity_domain_client(resource)
        client.delete_dynamic_resource_group(
            dynamic_resource_group_id=resource["identifier"],
            force_delete=True
        )

    def force_delete_app(self, resource):
        client = self._get_identity_domain_client(resource)
        app_id = resource["identifier"]

        # Deactivate first (required for Fusion/system apps)
        patch = PatchOp(
            schemas=["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            operations=[
                Operations(op="REPLACE", path="active", value=False),
            ],
        )

        try:
            client.patch_app(app_id=app_id, patch_op=patch)
            self.logger.info("Deactivated app %s before delete", app_id)
        except Exception as e:
            self.logger.warning("Deactivate failed (may already be inactive) %s: %s", app_id, e)

        client.delete_app(app_id=app_id, force_delete=True)
        self.logger.info("Deleted app %s", app_id)

    # -------------------------------------------------------------
    # CLASSIC POLICY DELETE
    # -------------------------------------------------------------

    def _get_tenancy_home_region_name(self):
        if self._home_region:
            return self._home_region

        import oci
        identity_client = oci.identity.IdentityClient(self.config, signer=self.signer)
        tenancy_id = self.config["tenancy"]
        tenancy = identity_client.get_tenancy(tenancy_id).data
        home_region_key = tenancy.home_region_key
        region_subscriptions = identity_client.list_region_subscriptions(tenancy_id).data

        for reg in region_subscriptions:
            if reg.region_key == home_region_key:
                self._home_region = reg.region_name
                return self._home_region

        raise Exception("Unable to determine tenancy home region")

    def force_delete_policy(self, resource):
        policy_id = resource["identifier"]
        home_region = self._get_tenancy_home_region_name()

        if home_region not in self.clients:
            original_region = self.config.get("region")
            self.config["region"] = home_region
            self.signer.region = home_region
            self.clients[home_region] = ClientBundle(self.config, self.signer)
            self.config["region"] = original_region

        self.clients[home_region].identity_client.delete_policy(policy_id=policy_id)

    # -------------------------------------------------------------
    # BULK MOVE
    # -------------------------------------------------------------

    def _try_bulk_one(self, resource, region, target):
        try:
            rtype = resource["resource_type"]
            ocid = resource["identifier"]

            bulk_resource = {
                "entityType": rtype,
                "identifier": ocid,
            }

            details = BulkMoveResourcesDetails(
                target_compartment_id=target,
                resources=[bulk_resource],
            )

            self.clients[region].identity_client.bulk_move_resources(
                resource["compartment_id"], details
            )

            return True

        except ServiceError:
            return False

        except Exception:
            return False

    # -------------------------------------------------------------
    # SDK MOVE METHODS (UNCHANGED)
    # -------------------------------------------------------------

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