#!/usr/bin/python3.11
import logging
from http import HTTPStatus
from collections.abc import Callable
from typing import Dict, List, Optional, Tuple
from oci import Signer
from oci.identity.models import BulkMoveResourcesDetails
from oci.exceptions import ServiceError
from oci.identity_domains.models import PatchOp, Operations
from ..base import BaseAction
from ..result import Result


class Deleter(BaseAction):
    SUPPORTED_RESOURCE_TYPE_ATTRS = (
        "BULK_SUPPORTED_TYPES",
        "MOVE_SPECS",
        "FORCE_DELETE_TYPES",
    )

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

    MOVE_SPECS = {
        "LogGroup": (
            "logging_management_client",
            "change_log_group_compartment",
        ),
        "DevOpsProject": (
            "devops_client",
            "change_project_compartment",
        ),
        "DevOpsBuildPipeline": (
            "devops_client",
            "change_build_pipeline_compartment",
        ),
        "DevOpsDeployPipeline": (
            "devops_client",
            "change_deploy_pipeline_compartment",
        ),
        "DevOpsRepository": (
            "devops_client",
            "change_repository_compartment",
        ),
        "IntegrationInstance": (
            "integration_client",
            "change_integration_instance_compartment",
        ),
        "Bastion": (
            "bastion_client",
            "change_bastion_compartment",
        ),
    }
    MOVE_SPEC_TYPES = set(MOVE_SPECS)

    # Keys from self.force_delete_handlers (metadata only)
    FORCE_DELETE_TYPES = {
        "User",
        "Group",
        "DynamicResourceGroup",
        "App",
        "Policy",
    }

    @classmethod
    def supported_delete_display_map(cls) -> dict[str, str]:
        """
        Returns {normalized_key: display_name} for all Delete-supported resource types.
        """
        return cls.supported_display_map()

    @classmethod
    def supported_force_display_map(cls) -> dict[str, str]:
        """
        Returns {normalized_key: display_name} for force-delete resource types only.
        """
        return {cls.normalize_resource_type(t): t for t in cls.FORCE_DELETE_TYPES if t}

    @classmethod
    def supported_norm_keys(cls):
        return super().supported_norm_keys()

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
        super().__init__(
            config=config,
            signer=signer,
            handler=handler,
            log_level=log_level,
            regions=regions,
            signer_factory=signer_factory,
            logger_name=__name__,
            require_region_without_regions=True,
            allow_signer_factory_for_regions=True,
            restore_signer_region_after_build=False,
        )
        self.quarantine_cmp = quarantine_cmp

        self.force_delete_handlers = {
            "User": self.force_delete_user,
            "Group": self.force_delete_group,
            "DynamicResourceGroup": self.force_delete_dynamic_resource_group,
            "App": self.force_delete_app,
            "Policy": self.force_delete_policy,
        }

        self.force_delete_types = list(self.force_delete_handlers.keys())

        self.logger.info("Deleter initialized")

    # Delete is the entry point to this class, intended to either move the resource
    # to a compartment to await deletion, or force/bulk delete depending on the type
    def delete(self, resource: Dict, **kwargs) -> Result:
        region = kwargs.get("region")
        target = kwargs.get("target_compartment_id", self.quarantine_cmp)
        return self._delete_single(resource, region, target)

    # Backwards-compatible batch alias for older call sites.
    def move(self, resources: List[Dict], **kwargs) -> Result:
        region = kwargs.get("region")
        target = kwargs.get("target_compartment_id", self.quarantine_cmp)
        last_result: Result = Result(
            HTTPStatus.BAD_REQUEST,
            message="No resources supplied for delete operation",
        )

        for r in resources:
            last_result = self._delete_single(r, region, target)

        return last_result


    # -------------------------------------------------------------
    # REGION CLIENT CREATION
    # -------------------------------------------------------------

    def create_clients(self, regions) -> dict:
        return self._create_clients(
            regions,
            require_region_without_regions=True,
            allow_signer_factory_for_regions=True,
        )

    def _delete_single(self, resource, region, target) -> Result:
        rtype = resource.get("resource_type")
        ocid = resource.get("identifier")
        metadata = {
            "resource_type": rtype,
            "identifier": ocid,
        }
        last_error: Optional[Result] = None

        if rtype in self.force_delete_handlers:
            try:
                result = self.force_delete_handlers[rtype](resource)
                self.logger.info("Force delete succeeded for %s (%s)", rtype, ocid)
                return result
            except Exception as exc:
                self.logger.exception("Force delete failed for %s (%s)", rtype, ocid)
                return Result(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    message=str(exc),
                    metadata={"method": "force", **metadata},
                )

        region = region or resource.get("region") or resource.get("home_region")
        if not region:
            return Result(
                HTTPStatus.BAD_REQUEST,
                message=f"Region missing for {rtype} {ocid}",
                metadata=metadata,
            )
        if region not in self.clients:
            return Result(
                HTTPStatus.NOT_FOUND,
                message=f"No client configured for region {region}",
                metadata={"resource_type": rtype, "identifier": ocid, "region": region},
            )

        metadata["region"] = region

        # Bulk path
        if rtype in type(self).BULK_SUPPORTED_TYPES:
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

        move_spec = type(self).MOVE_SPECS.get(rtype)
        if move_spec:
            try:
                response = self._move_with_sdk_spec(
                    move_spec,
                    identifier=ocid,
                    region=region,
                    target_compartment_id=target,
                )
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
            "Delete failed after all attempts for %s (%s)", rtype, ocid
        )
        return last_error or Result(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            message=f"Delete failed after all attempts for {rtype} {ocid}",
            metadata=metadata,
        )

    # -------------------------------------------------------------
    # MULTI-DOMAIN RESOLUTION
    # -------------------------------------------------------------

    def _get_identity_domain_client(self, resource):
        import oci

        resource_ocid = resource["identifier"]
        rtype = resource.get("resource_type")

        if resource_ocid in self._domain_client_cache:
            return self._domain_client_cache[resource_ocid]

        for client in self._iter_identity_domain_clients(resource):
            try:
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

    def force_delete_policy(self, resource):
        policy_id = resource["identifier"]
        home_region = self._get_tenancy_home_region_name()

        if home_region not in self.clients:
            self.clients[home_region] = self._build_client_for_region(home_region)

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
        action_region = None
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

            action_region, action_clients = self._get_home_region_client_bundle()
            response = action_clients.identity_client.bulk_move_resources(
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
                        "action_region": action_region,
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
                        "action_region": action_region or region,
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
                        "action_region": action_region or region,
                    },
                ),
                False,
            )

    # -------------------------------------------------------------
    # SDK MOVE SPEC EXECUTION
    # -------------------------------------------------------------

    def _move_with_sdk_spec(
        self,
        move_spec: tuple[str, str],
        identifier,
        region,
        target_compartment_id,
    ) -> Result:
        client_attr, method_name = move_spec
        client = getattr(self.clients[region], client_attr)
        method = getattr(client, method_name)
        response = method(identifier, {"compartmentId": target_compartment_id})
        return Result(response.status)
