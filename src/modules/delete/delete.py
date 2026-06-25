#!/usr/bin/python3.11
import logging
from http import HTTPStatus
from collections.abc import Callable
from typing import Dict, List, Optional, Tuple
import re
from oci import Signer, Response
from oci.identity.models import BulkMoveResourcesDetails
from oci.exceptions import ServiceError
from oci.identity_domains import IdentityDomainsClient
from oci.identity_domains.models import PatchOp, Operations
from .client_bundle import ClientBundle
from .result import Result
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
       # Keys from self.move_tree (metadata only)
    MOVE_TREE_TYPES = {
        "LogGroup",
        "DevOpsProject",
        "DevOpsBuildPipeline",
        "DevOpsDeployPipeline",
        "DevOpsRepository",
        "IntegrationInstance",
        "Bastion",
    }

    # Keys from self.force_delete_tree (metadata only)
    FORCE_DELETE_TYPES = {
        "User",
        "Group",
        "DynamicResourceGroup",
        "App",
        "Policy",
    }

        ######## SUPPORTED RESOURCE TYPE FOR HANDLERS #########


    @staticmethod
    def normalize_resource_type(rtype: Optional[str]) -> str:
        # same normalization rule as Extender
        return re.sub(r'[_\-\s]', '', (rtype or '').strip().lower()) if rtype else ""

    @classmethod
    def supported_delete_display_map(cls) -> dict[str, str]:
        """
        Returns {normalized_key: display_name} for all Delete-supported resource types.
        """
        all_delete = set(cls.BULK_SUPPORTED_TYPES) | set(cls.MOVE_TREE_TYPES) | set(cls.FORCE_DELETE_TYPES)
        return {cls.normalize_resource_type(t): t for t in all_delete if t}

    @classmethod
    def supported_force_display_map(cls) -> dict[str, str]:
        """
        Returns {normalized_key: display_name} for force-delete resource types only.
        """
        return {cls.normalize_resource_type(t): t for t in cls.FORCE_DELETE_TYPES if t}

    @classmethod
    def supported_norm_keys(cls):
        return (
            set(cls.supported_delete_display_map().keys()) |
            set(cls.supported_force_display_map().keys())
        )

    def __init__(
        self,
        config: dict[str, str],
        quarantine_cmp: str,
        signer: Signer | None,
        handler: logging.Handler = logging.StreamHandler(),
        log_level: int | str = logging.INFO,
        regions=None,
        signer_factory: Callable[[str | None], Signer] | None = None,
    ):
        self.logger = log_factory(__name__, log_level, handler)
        self.config = config
        self.signer: Signer | None = signer
        self.signer_factory = signer_factory
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

        self.force_delete_types = list(self.force_delete_tree.keys())

        self.logger.info("Deleter initialized")




    # -------------------------------------------------------------
    # REGION CLIENT CREATION
    # -------------------------------------------------------------

    def create_clients(self, regions) -> dict:
        clients = {}
        original_region = self.config.get("region")
        original_signer_region = getattr(self.signer, "region", None)

        def _bundle_for(region_name: str) -> ClientBundle:
            region_config = self.config.copy()
            region_config["region"] = region_name
            regional_signer = self.signer_factory(region_name) if self.signer_factory else self.signer
            if regional_signer is not None and not self.signer_factory:
                regional_signer.region = region_name
            return ClientBundle(region_config, regional_signer)

        if not regions:
            if not original_region:
                raise ValueError("Config missing 'region' for client creation")
            regional_signer = self.signer_factory(original_region) if self.signer_factory else self.signer
            if regional_signer is not None and not self.signer_factory:
                regional_signer.region = original_region
            clients[original_region] = ClientBundle(self.config, regional_signer)
        else:
            if self.signer is None and self.signer_factory is None:
                raise ValueError("Signer is required when creating multi-region clients")
            for r in regions:
                clients[r] = _bundle_for(r)

        if original_region is not None:
            self.config["region"] = original_region
        if self.signer is not None and original_signer_region is not None:
            self.signer.region = original_signer_region

        return clients

    # -------------------------
    # Entry point
    # -------------------------
    def move(self, resources: List[Dict], **kwargs) -> Result:
        region = kwargs.get("region")
        target = kwargs.get("target_compartment_id", self.quarantine_cmp)

        last_result: Result = Result(
            HTTPStatus.BAD_REQUEST,
            message="No resources supplied for move operation",
        )

        for r in resources:
            last_result = self._move_or_force_delete_single(r, region, target)

        return last_result

    def _move_or_force_delete_single(self, resource, region, target) -> Result:
        rtype = resource.get("resource_type")
        ocid = resource.get("identifier")
        region = region or resource.get("region") or resource.get("home_region")
        if not region:
            return Result(
                HTTPStatus.BAD_REQUEST,
                message=f"Region missing for {rtype} {ocid}",
                metadata={"resource_type": rtype, "identifier": ocid},
            )
        if region not in self.clients:
            return Result(
                HTTPStatus.NOT_FOUND,
                message=f"No client configured for region {region}",
                metadata={"resource_type": rtype, "identifier": ocid, "region": region},
            )
        metadata = {
            "resource_type": rtype,
            "identifier": ocid,
            "region": region,
        }
        last_error: Optional[Result] = None

        if rtype in self.force_delete_tree:
            try:
                result = self.force_delete_tree[rtype](resource)
                self.logger.info("Force delete succeeded for %s (%s)", rtype, ocid)
                return result
            except Exception as exc:
                self.logger.exception("Force delete failed for %s (%s)", rtype, ocid)
                last_error = Result(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    message=str(exc),
                    metadata={"method": "force", **metadata},
                )

        # Bulk path
        elif rtype in Deleter.BULK_SUPPORTED_TYPES:
            bulk_result, bulk_success = self._try_bulk_one(resource, region, target)
            if bulk_success and bulk_result:
                self.logger.info("Bulk move succeeded for %s (%s)", rtype, ocid)
                bulk_result.metadata.update({"method": "bulk", **metadata})
                return bulk_result

            if bulk_result:
                last_error = bulk_result
            self.logger.error(
                "Bulk supported resource failed via bulk: %s (%s)", rtype, ocid
            )

        func = self.move_tree.get(rtype)
        if func:
            try:
                response = func(identifier=ocid, region=region, target_compartment_id=target)
                self.logger.info("SDK move succeeded for %s (%s)", rtype, ocid)
                status = getattr(response, "status", HTTPStatus.OK)
                headers = getattr(response, "headers", {}) or {}
                work_request = headers.get("opc-work-request-id")
                return Result(
                    status=status,
                    work_request=work_request,
                    metadata={"method": "sdk", **metadata},
                )
            except Exception:
                self.logger.exception("SDK move failed for %s (%s)", rtype, ocid)
                last_error = Result(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    message=f"SDK move failed for {rtype} {ocid}",
                    metadata={"method": "sdk", **metadata},
                )

        self.logger.error(
            "Move/force delete failed after all attempts for %s (%s)", rtype, ocid
        )
        return last_error or Result(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            message=f"Move failed after all attempts for {rtype} {ocid}",
            metadata=metadata,
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

        for domain in domains:

            domain_region = domain.home_region
            domain_endpoint = domain.url

            if not domain_region or not domain_endpoint:
                continue

            try:
                domain_config = dict(self.config)
                domain_config["region"] = domain_region
                domain_signer = self.signer_factory(domain_region) if self.signer_factory else self.signer
                if domain_signer is not None and not self.signer_factory:
                    domain_signer.region = domain_region

                client = IdentityDomainsClient(
                    domain_config,
                    signer=domain_signer,
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

                return client

            except oci.exceptions.ServiceError as e:
                if e.status == 404:
                    continue
                raise

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
        return Result(
            status=HTTPStatus.OK,
            metadata={"method": "force", "resource_type": "User", "identifier": user_id},
        )

    def force_delete_group(self, resource):
        client = self._get_identity_domain_client(resource)
        group_id = resource["identifier"]
        client.delete_group(group_id=group_id, force_delete=True)
        return Result(
            status=HTTPStatus.OK,
            metadata={"method": "force", "resource_type": "Group", "identifier": group_id},
        )

    def force_delete_dynamic_resource_group(self, resource):
        client = self._get_identity_domain_client(resource)
        drg_id = resource["identifier"]
        client.delete_dynamic_resource_group(
            dynamic_resource_group_id=drg_id,
            force_delete=True
        )
        return Result(
            status=HTTPStatus.OK,
            metadata={"method": "force", "resource_type": "DynamicResourceGroup", "identifier": drg_id},
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
        return Result(
            status=HTTPStatus.OK,
            metadata={"method": "force", "resource_type": "App", "identifier": app_id},
        )

    # -------------------------------------------------------------
    # CLASSIC POLICY DELETE
    # -------------------------------------------------------------

    def _get_tenancy_home_region_name(self):
        if self._home_region:
            return self._home_region

        if self.signer is None:
            raise ValueError("Signer is required to resolve tenancy home region")

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
            region_config = dict(self.config)
            region_config["region"] = home_region
            region_signer = self.signer_factory(home_region) if self.signer_factory else self.signer
            if region_signer is not None and not self.signer_factory:
                region_signer.region = home_region
            self.clients[home_region] = ClientBundle(region_config, region_signer)

        self.clients[home_region].identity_client.delete_policy(policy_id=policy_id)
        return Result(
            status=HTTPStatus.OK,
            metadata={"method": "force", "resource_type": "Policy", "identifier": policy_id},
        )

    # -------------------------------------------------------------
    # BULK MOVE
    # -------------------------------------------------------------

    def _try_bulk_one(
        self, resource, region, target
    ) -> Tuple[Optional[Result], bool]:
        try:
            rtype = resource["resource_type"]
            ocid = resource["identifier"]

            bulk_resource = {
                "entityType": rtype,
                "identifier": ocid,
            }

            # Buckets need metadata
            if rtype == "Bucket":
                namespace = (
                    resource.get("namespace")
                    or resource.get("namespace_name")
                    or self.clients[region]
                    .object_storage_client.get_namespace()
                    .data
                )

                bucket_name = (
                    resource.get("identifier_name")
                    or resource.get("display_name")
                    or resource.get("bucket_name")
                )

                if not bucket_name:
                    self.logger.error("Bucket name missing for %s", ocid)
                    return (
                        Result(
                            status=HTTPStatus.BAD_REQUEST,
                            message=f"Bucket name missing for {ocid}",
                            metadata={
                                "method": "bulk",
                                "resource_type": rtype,
                                "identifier": ocid,
                                "region": region,
                            },
                        ),
                        False,
                    )

                bulk_resource["metadata"] = {
                    "namespaceName": namespace,
                    "bucketName": bucket_name,
                }

                self.logger.info(
                    "Bulk bucket payload → ocid=%s name=%s namespace=%s",
                    ocid,
                    bucket_name,
                    namespace,
                )

            details = BulkMoveResourcesDetails(
                target_compartment_id=target,
                resources=[bulk_resource],
            )

            response = self.clients[region].identity_client.bulk_move_resources(
                resource["compartment_id"], details
            )

            headers = getattr(response, "headers", {}) or {}
            work_request = headers.get("opc-work-request-id")

            return (
                Result(
                    status=response.status,
                    work_request=work_request,
                    metadata={
                        "method": "bulk",
                        "resource_type": rtype,
                        "identifier": ocid,
                        "region": region,
                    },
                ),
                True,
            )

        except ServiceError as e:
            rtype = resource.get("resource_type")
            ocid = resource.get("identifier")
            self.logger.info(
                "Bulk move rejected by OCI for %s (%s): %s",
                rtype,
                ocid,
                e.message,
            )
            return (
                Result(
                    status=e.status or HTTPStatus.BAD_REQUEST,
                    message=e.message,
                    metadata={
                        "method": "bulk",
                        "resource_type": rtype,
                        "identifier": ocid,
                        "region": region,
                    },
                ),
                False,
            )

        except Exception:
            rtype = resource.get("resource_type")
            ocid = resource.get("identifier")
            self.logger.exception("Bulk move crashed for %s", ocid)
            return (
                Result(
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    message=f"Bulk move crashed for {ocid}",
                    metadata={
                        "method": "bulk",
                        "resource_type": rtype,
                        "identifier": ocid,
                        "region": region,
                    },
                ),
                False,
            )

    # -------------------------------------------------------------
    # SDK MOVE METHODS (UNCHANGED)
    # -------------------------------------------------------------

    def move_log_group(self, identifier, region, target_compartment_id, **_) -> Result:
        response: Response = self.clients[
            region
        ].logging_management_client.change_log_group_compartment(
            identifier, {"compartmentId": target_compartment_id}
        )
        return Result(response.status)

    def move_devops_project(self, identifier, region, target_compartment_id, **_) -> Result:
        response: Response = self.clients[region].devops_client.change_project_compartment(
            identifier, {"compartmentId": target_compartment_id}
        )
        return Result(response.status)

    def move_devops_build_pipeline(self, identifier, region, target_compartment_id, **_) -> Result:
        response: Response = self.clients[region].devops_client.change_build_pipeline_compartment(
            identifier, {"compartmentId": target_compartment_id}
        )
        return Result(response.status)

    def move_devops_deploy_pipeline(self, identifier, region, target_compartment_id, **_) -> Result:
        response: Response = self.clients[region].devops_client.change_deploy_pipeline_compartment(
            identifier, {"compartmentId": target_compartment_id}
        )
        return Result(response.status)

    def move_devops_repository(self, identifier, region, target_compartment_id, **_) -> Result:
        response: Response = self.clients[region].devops_client.change_repository_compartment(
            identifier, {"compartmentId": target_compartment_id}
        )
        return Result(response.status)

    def move_integration_instance(self, identifier, region, target_compartment_id, **_) -> Result:
        response: Response = self.clients[
            region
        ].integration_client.change_integration_instance_compartment(
            identifier, {"compartmentId": target_compartment_id}
        )
        return Result(response.status)

    def move_bastion(self, identifier, region, target_compartment_id, **_) -> Result:
        response: Response = self.clients[region].bastion_client.change_bastion_compartment(
            identifier, {"compartmentId": target_compartment_id}
        )
        return Result(response.status)
