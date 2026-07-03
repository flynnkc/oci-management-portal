import logging
import copy
import re
from datetime import datetime, timedelta
from http import HTTPStatus
from collections.abc import Callable
from typing import Any, Optional, Tuple

import oci
from oci.exceptions import ServiceError
from oci.identity.models import (
    BulkEditTagsDetails,
    BulkEditOperationDetails,
    BulkEditResource,
)
from oci.identity_domains import IdentityDomainsClient
from oci.identity_domains.models import PatchOp, Operations
from oci.object_storage.models import UpdateBucketDetails
from oci.logging.models import UpdateLogGroupDetails
from oci.resource_manager.models import UpdateStackDetails
from oci.events.models import UpdateRuleDetails
from oci.monitoring.models import UpdateAlarmDetails
from oci.file_storage.models import UpdateFileSystemDetails, UpdateMountTargetDetails
from oci.email.models import UpdateEmailDomainDetails, UpdateSenderDetails
from oci.ons.models import TopicAttributesDetails, UpdateSubscriptionDetails
#from oci.vault.models import UpdateSecretDetails
#from oci.key_management.models import UpdateVaultDetails, UpdateKeyDetails
from oci.devops.models import (
    UpdateProjectDetails,
    UpdateBuildPipelineDetails,
    UpdateDeployPipelineDetails,
    UpdateRepositoryDetails,
)
from oci.core.models import (
    UpdateBootVolumeBackupDetails,
    UpdateVolumeBackupDetails,
    UpdateVolumeGroupDetails,
    UpdateVolumeGroupBackupDetails,
    UpdateVcnDetails,
    UpdateSubnetDetails,
    UpdateInternetGatewayDetails,
    UpdateLocalPeeringGatewayDetails,
    UpdateNatGatewayDetails,
    UpdateNetworkSecurityGroupDetails,
    UpdatePublicIpDetails,
    UpdateRouteTableDetails,
    UpdateSecurityListDetails,
    UpdateServiceGatewayDetails,
    UpdateCrossConnectDetails,
    UpdateCrossConnectGroupDetails,
    UpdateIPSecConnectionDetails,
    UpdateRemotePeeringConnectionDetails,
    UpdateVirtualCircuitDetails,
    UpdateClusterNetworkDetails,
    UpdateDedicatedVmHostDetails,
    UpdateImageDetails,
    UpdateInstanceConfigurationDetails,
    UpdateInstancePoolDetails,
)

from oci.database.models import (
    UpdateAutonomousContainerDatabaseDetails,
    UpdateAutonomousExadataInfrastructureDetails,
    UpdateDbSystemDetails,
    UpdateVmClusterDetails,
    UpdateExadataInfrastructureDetails,
    UpdateBackupDestinationDetails,
)

from oci.os_management_hub.models import (
    UpdateManagedInstanceGroupDetails,
    UpdateScheduledJobDetails,
    UpdateSoftwareSourceDetails,
)

from oci.integration.models import UpdateIntegrationInstanceDetails
from oci.oda.models import UpdateOdaInstanceDetails
from oci.bastion.models import UpdateBastionDetails
from ..client_bundle import ClientBundle
from ..lazy_client_map import LazyClientMap
from ..result import Result
from ...utils import log_factory


OCID_REGION_CODES = {
    "iad": "us-ashburn-1",
    "phx": "us-phoenix-1",
    "sjc": "us-sanjose-1",
    "fra": "eu-frankfurt-1",
    "lhr": "uk-london-1",
    "hyd": "in-hyderabad-1",
    "yyz": "ca-toronto-1",
    "nrt": "ap-tokyo-1",
    "icn": "ap-seoul-1",
}

class Extender:
    BULK_EXTEND_SUPPORTED_TYPES = {
        "Instance",
        "Volume",
        "BootVolume",
        "AutonomousDatabase",
        "AnalyticsInstance",
        "FunctionsApplication",
        "LoadBalancer",
        "Vault",
        "Key",
        "Stream",
        "TagNamespace",
    }
    UPDATE_TAG_TREE_TYPES = {
        "bucket",
        "devopsproject",
        "devopsbuildpipeline",
        "devopsdeploypipeline",
        "devopsrepository",
        "loggroup",
        "ormstack",
        "integrationinstance",
        "odainstance",
        "bastion",
        "eventrule",
        "alarm",
        "filesystem",
        "mounttarget",
        "emailsender",
        "emaildomain",
        "onstopic",
        "onssubscription",
        # "vaultsecret",
        # "vault",
        # "key",
        # "osmsmanagedinstancegroup",
        # "osmsscheduledjob",
        # "osmssoftwaresource",
        "autonomouscontainerdatabase",
        "autonomousexadatainfrastructure",
        "dbsystem",
        "exadatainfrastructure",
        "backupdestination",
        "vmcluster",
        "bootvolumebackup",
        "volumebackup",
        "volumegroup",
        "volumegroupbackup",
        "vcn",
        "subnet",
        "internetgateway",
        "natgateway",
        "localpeeringgateway",
        "networksecuritygroup",
        "publicip",
        "routetable",
        "securitylist",
        "servicegateway",
        "crossconnect",
        "crossconnectgroup",
        "ipsecconnection",
        "remotepeeringconnection",
        "virtualcircuit",
        "clusternetwork",
        "dedicatedvmhost",
        "image",
        "instanceconfiguration",
        "instancepool",
    }
    IDENTITY_EXTEND_SUPPORTED_TYPES = {
        "User",
        "Group",
        "DynamicResourceGroup",
        "App",
        "Policy",
    }
        ############ SUPPORTED RESOURCE TYPE FOR HANDLERS ##########
    @staticmethod
    def normalize_resource_type(rtype: Optional[str]) -> str:
        return re.sub(r'[_\-\s]', '', (rtype or '').strip().lower()) if rtype else ""

    @classmethod
    def supported_extend_norm_keys(cls) -> set[str]:

        all_extend = (
            set(cls.BULK_EXTEND_SUPPORTED_TYPES)
            | set(cls.UPDATE_TAG_TREE_TYPES)
            | set(cls.IDENTITY_EXTEND_SUPPORTED_TYPES)
        )
        return {cls.normalize_resource_type(t) for t in all_extend if t}

    def __init__(
        self,
        config,
        signer,
        tag_namespace,
        tag_key,
        extend_period=timedelta(days=30),
        handler: logging.Handler = logging.StreamHandler(),
        log_level: int | str = logging.INFO,
        regions=None,
        signer_factory: Callable[[str | None], Any] | None = None,
    ):
        self.logger = log_factory(__name__, log_level, handler)
        self.config = config
        self.signer = signer
        self.signer_factory = signer_factory
        self.tag_namespace = tag_namespace
        self.tag_key = tag_key
        self.extend_period = extend_period
        self.clients = self._create_clients(regions)
        self._domain_client_cache = {}
        self._home_region = None
        self.update_tag_tree = {
            "bucket": self.update_bucket,
            "devopsproject": self.update_devops_project,
            "devopsbuildpipeline": self.update_devops_build_pipeline,
            "devopsdeploypipeline": self.update_devops_deploy_pipeline,
            "devopsrepository": self.update_devops_repository,
            "loggroup": self.update_log_group,
            "resourcemanagerstack": self.update_stack,
            "ormstack": self.update_stack,
            "integrationinstance": self.update_integration,
            "odainstance": self.update_oda,
            "bastion": self.update_bastion,
            "eventrule": self.update_event_rule,
            "alarm": self.update_alarm,
            "filesystem": self.update_file_system,
            "mounttarget": self.update_mount_target,
            "emailsender": self.update_email_sender,
            "emaildomain": self.update_email_domain,
            "onstopic": self.update_topic,
            "onssubscription": self.update_subscription,
            # #"vaultsecret": self.update_vault_secret,
            # "vault": self.update_vault,
            # "key": self.update_key,
            ###### OS HUB *****

            # "osmsmanagedinstancegroup": self.update_managed_instance_group,
            # "osmsscheduledjob": self.update_scheduled_job,
            # "osmssoftwaresource": self.update_software_source,
            ####Database Resoources ###
            "autonomouscontainerdatabase": self.update_autonomous_container_database,
            "autonomousexadatainfrastructure": self.update_autonomous_exadata_infrastructure,
            "dbsystem": self.update_db_system,
            "exadatainfrastructure": self.update_exadata_infrastructure,
            "backupdestination": self.update_backup_destination, 
            "vmcluster": self.update_vm_cluster,

            ##### OCI CORE ####
            "bootvolumebackup": self.update_boot_volume_backup,
            "volumebackup": self.update_volume_backup,
            "volumegroup": self.update_volume_group,
            "volumegroupbackup": self.update_volume_group_backup,
            "vcn": self.update_vcn,
            "subnet": self.update_subnet,
            "internetgateway": self.update_internet_gateway,
            "natgateway": self.update_nat_gateway,
            "localpeeringgateway": self.update_local_peering_gateway,
            "networksecuritygroup": self.update_network_security_group,
            "publicip": self.update_public_ip,
            "routetable": self.update_route_table,
            "securitylist": self.update_security_list,
            "servicegateway": self.update_service_gateway,
            "crossconnect": self.update_cross_connect,
            "crossconnectgroup": self.update_cross_connect_group,
            "ipsecconnection": self.update_ipsec_connection,
            "remotepeeringconnection": self.update_remote_peering_connection,
            "virtualcircuit": self.update_virtual_circuit,
            "clusternetwork": self.update_cluster_network,
            "dedicatedvmhost": self.update_dedicated_vm_host,
            "image": self.update_image,
            "instanceconfiguration": self.update_instance_configuration,
            "instancepool": self.update_instance_pool,
        }
        self.logger.info("Unified Extender initialized")

    def _normalize_resource_type(self, rtype: Optional[str]) -> str:
        return re.sub(r'[_\-\s]', '', (rtype or '').strip().lower()) if rtype else ""

    def _get_tenancy_home_region_name(self):
        if self._home_region:
            return self._home_region

        if self.signer is None:
            raise ValueError("Signer is required to resolve tenancy home region")

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

    def _get_region(self, resource):
        ocid = resource.get("identifier")
        norm = self._normalize_resource_type(resource.get("resource_type"))
        identity_types = {
            "user", "group", "dynamicgroup", "dynamicresourcegroup", "confidentialapplication", "app", "policy"
        }
        region_hint = resource.get("region") or resource.get("home_region")
        if norm in identity_types:
            region = self._get_tenancy_home_region_name()
        else:
            region = region_hint or self.derive_region_from_ocid(ocid)
        if not region:
            return None
        if region not in self.clients:
            self.clients[region] = self._build_client_for_region(region)
        return region

    @staticmethod
    def derive_region_from_ocid(ocid: Optional[str]):
        if not ocid:
            return None
        match = re.search(r"\.oc1\.([a-z]+)\.", ocid)
        if match:
            return OCID_REGION_CODES.get(match.group(1))
        return None

    def _create_clients(self, regions):
        original_region = self.config.get("region")
        original_signer_region = getattr(self.signer, "region", None)
        allowed_regions = regions or ([original_region] if original_region else [])
        clients = LazyClientMap(allowed_regions, self._build_client_for_region)
        if regions:
            if self.signer is None:
                raise ValueError("Signer is required when creating clients for multiple regions")
        if original_region is not None:
            self.config["region"] = original_region
        if self.signer is not None and original_signer_region is not None:
            self.signer.region = original_signer_region
        return clients

    def _build_client_for_region(self, region: str) -> ClientBundle:
        if not region:
            raise ValueError("Region must be provided to build client bundle")
        region_config = self.config.copy()
        region_config["region"] = region
        signer = self.signer_factory(region) if self.signer_factory else self.signer
        original_signer_region = getattr(signer, "region", None)
        if signer is not None and not self.signer_factory:
            signer.region = region
        bundle = ClientBundle(region_config, signer)
        if signer is not None and not self.signer_factory and original_signer_region is not None:
            signer.region = original_signer_region
        return bundle

    def _get_identity_domains_client(self, resource):
        resource_ocid = resource["identifier"]
        norm = self._normalize_resource_type(resource.get("resource_type"))
        resource_compartment = resource.get("compartment_id")
        if resource_ocid in self._domain_client_cache:
            return self._domain_client_cache[resource_ocid]
        identity_client = oci.identity.IdentityClient(self.config, signer=self.signer)
        domains = identity_client.list_domains(
            compartment_id=resource_compartment,
            lifecycle_state="ACTIVE"
        ).data
        for domain in domains:
            try:
                domain_region = domain.home_region
                domain_endpoint = domain.url
                if not domain_region or not domain_endpoint:
                    continue
                domain_config = dict(self.config)
                domain_config["region"] = domain_region
                domain_signer = self.signer_factory(domain_region) if self.signer_factory else self.signer
                if domain_signer is not None and not self.signer_factory:
                    domain_signer.region = domain_region
                client = IdentityDomainsClient(
                    domain_config,
                    service_endpoint=domain_endpoint,
                    signer=domain_signer,
                )
                if norm == "user":
                    client.get_user(user_id=resource_ocid)
                elif norm == "group":
                    client.get_group(group_id=resource_ocid)
                elif norm in ("confidentialapplication", "app"):
                    client.get_app(app_id=resource_ocid)
                else:
                    continue
                self._domain_client_cache[resource_ocid] = client
                return client
            except oci.exceptions.ServiceError as e:
                if e.status == 404:
                    continue
                raise
        raise Exception(f"Unable to determine Identity Domain for {resource_ocid}")

    def extend(self, resource: dict) -> Result:
        ocid = resource.get("identifier")
        rtype = resource.get("resource_type", "")
        norm = self._normalize_resource_type(rtype)
        defined_tags = resource.get("defined_tags", {})
        region = self._get_region(resource)
        if not region:
            self.logger.error("Unable to determine region for %s", ocid)
            return Result(
                HTTPStatus.BAD_REQUEST,
                message=f"Region could not be derived for {ocid}",
                metadata={"identifier": ocid, "resource_type": rtype},
            )
        today = datetime.utcnow().date()
        new_value = (today + self.extend_period).strftime("%Y-%m-%d")
        # Identity Domain tags
        if norm in {"user", "group", "confidentialapplication", "app"}:
            return self._update_identity_resource(resource, norm, new_value)
        # Classic IAM dynamic group
        if norm in {"dynamicgroup", "dynamicresourcegroup"}:
            return self._update_dynamic_group_classic(resource, region, new_value)
        # Bulk
        if rtype in Extender.BULK_EXTEND_SUPPORTED_TYPES:
            bulk_result, bulk_success = self._try_bulk_extend(resource, region, new_value)
            if bulk_success and bulk_result:
                self.logger.info(
                    "Bulk extend succeeded for %s (%s)",
                    rtype, ocid
                )
                bulk_result.metadata.setdefault("method", "bulk")
                return bulk_result
            self.logger.error(
                "Bulk supported resource failed via bulk extend: %s (%s)",
                rtype, ocid
            )
            return bulk_result or Result(
                HTTPStatus.NOT_IMPLEMENTED,
                message=f"Bulk extend failed for {rtype} {ocid}",
                metadata={"identifier": ocid, "resource_type": rtype},
            )
        # Classic policy
        if norm == "policy":
            return self._update_policy_classic(resource, region, new_value)
        # SDK path (normalize keys)
        updater = self.update_tag_tree.get(norm)
        if not updater:
            self.logger.error(
                "No extend implementation for %s (%s)",
                rtype, ocid
            )
            return Result(
                HTTPStatus.NOT_IMPLEMENTED,
                message=f"No extender implementation for {rtype}",
                metadata={"identifier": ocid, "resource_type": rtype},
            )
        try:
            response = updater(resource, region, new_value, defined_tags)
            status = getattr(response, "status", response)
            metadata = {
                "identifier": ocid,
                "resource_type": rtype,
                "region": region,
                "method": "sdk",
            }
            return Result(
                status=status,
                message=f"Expiry extended to {new_value}",
                metadata=metadata,
            )
        except Exception:
            self.logger.exception(
                "SDK extend failed for %s (%s)",
                rtype, ocid
            )
            return Result(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                message=f"SDK extend failed for {rtype} {ocid}",
                metadata={
                    "identifier": ocid,
                    "resource_type": rtype,
                    "region": region,
                    "method": "sdk",
                },
            )

    def _try_bulk_extend(self, resource, region, new_value) -> Tuple[Optional[Result], bool]:
        ocid = resource.get("identifier")
        rtype = resource.get("resource_type")
        compartment_id = resource.get("compartment_id")
        if not compartment_id:
            self.logger.error(
                "Missing compartment_id for bulk extend %s (%s)",
                rtype, ocid
            )
            return (
                Result(
                    HTTPStatus.BAD_REQUEST,
                    message=f"Missing compartment_id for {ocid}",
                    metadata={"identifier": ocid, "resource_type": rtype},
                ),
                False,
            )
        try:
            bulk_resource = BulkEditResource(
                id=resource["identifier"],
                resource_type=resource["resource_type"],
                metadata={}
            )
            bulk_operation = BulkEditOperationDetails(
                operation_type="ADD_OR_SET",
                defined_tags={
                    self.tag_namespace: {
                        self.tag_key: new_value
                    }
                }
            )
            details = BulkEditTagsDetails(
                compartment_id=resource["compartment_id"],
                resources=[bulk_resource],
                bulk_edit_operations=[bulk_operation],
            )
            response = self.clients[region].identity_client.bulk_edit_tags(
                bulk_edit_tags_details=details
            )
            status = getattr(response, "status", HTTPStatus.OK)
            headers = getattr(response, "headers", {}) or {}
            work_request = headers.get("opc-work-request-id")
            return (
                Result(
                    status=status,
                    work_request=work_request,
                    message=f"Expiry extended to {new_value}",
                    metadata={
                        "identifier": ocid,
                        "resource_type": rtype,
                        "region": region,
                        "method": "bulk",
                    },
                ),
                True,
            )
        except ServiceError as e:
            self.logger.info(
                "Bulk extend rejected by OCI for %s (%s): %s",
                rtype, ocid, e.message
            )
            return (
                Result(
                    status=e.status or HTTPStatus.BAD_REQUEST,
                    message=e.message,
                    metadata={
                        "identifier": ocid,
                        "resource_type": rtype,
                        "region": region,
                        "method": "bulk",
                    },
                ),
                False,
            )
        except Exception:
            self.logger.exception(
                "Bulk extend crashed for %s (%s)",
                rtype, ocid
            )
            return (
                Result(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    message=f"Bulk extend crashed for {ocid}",
                    metadata={
                        "identifier": ocid,
                        "resource_type": rtype,
                        "region": region,
                        "method": "bulk",
                    },
                ),
                False,
            )

    def _update_identity_resource(self, resource, norm, new_value):
        client = self._get_identity_domains_client(resource)
        resource_ocid = resource["identifier"]
        defined_tags = copy.deepcopy(resource.get("defined_tags", {}))
        defined_tags.setdefault(self.tag_namespace, {})
        defined_tags[self.tag_namespace][self.tag_key] = new_value
        tag_list = self._convert_defined_tags_to_list(defined_tags)
        patch = PatchOp(
            schemas=["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            operations=[
                Operations(
                    op="REPLACE",
                    path="urn:ietf:params:scim:schemas:oracle:idcs:extension:OCITags:definedTags",
                    value=tag_list,
                ),
            ],
        )
        if norm == "user":
            response = client.patch_user(user_id=resource_ocid, patch_op=patch)
        elif norm == "group":
            response = client.patch_group(group_id=resource_ocid, patch_op=patch)
        elif norm in ("confidentialapplication", "app"):
            response = client.patch_app(
                app_id=resource_ocid,
                patch_op=patch,
            )
        else:
            raise Exception("Unsupported identity type")
        status = getattr(response, "status", HTTPStatus.OK)
        return Result(
            status=status,
            message=f"Expiry extended to {new_value}",
            metadata={
                "identifier": resource_ocid,
                "resource_type": norm,
                "method": "identity",
            },
        )

    def _update_dynamic_group_classic(self, resource, region, new_value):
        defined_tags = copy.deepcopy(resource.get("defined_tags", {}))
        defined_tags.setdefault(self.tag_namespace, {})
        defined_tags[self.tag_namespace][self.tag_key] = new_value
        freeform_tags = resource.get("freeformTags", {}) or {}
        resp = self.clients[region].identity_client.update_dynamic_group(
            dynamic_group_id=resource["identifier"],
            update_dynamic_group_details=oci.identity.models.UpdateDynamicGroupDetails(
                defined_tags=defined_tags,
                freeform_tags=freeform_tags,
            ),
        )
        status = getattr(resp, "status", HTTPStatus.OK)
        return Result(
            status=status,
            message=f"Expiry extended to {new_value}",
            metadata={
                "identifier": resource["identifier"],
                "resource_type": "dynamicresourcegroup",
                "region": region,
                "method": "identity",
            },
        )

    def _update_policy_classic(self, resource, region, new_value):
        defined_tags = copy.deepcopy(resource.get("defined_tags", {}))
        defined_tags.setdefault(self.tag_namespace, {})
        defined_tags[self.tag_namespace][self.tag_key] = new_value
        update_details = oci.identity.models.UpdatePolicyDetails(
            defined_tags=defined_tags,
            freeform_tags=resource.get("freeformTags", {}) or {}
        )
        response = self.clients[region].identity_client.update_policy(
            policy_id=resource["identifier"],
            update_policy_details=update_details,
        )
        status = getattr(response, "status", HTTPStatus.OK)
        return Result(
            status=status,
            message=f"Expiry extended to {new_value}",
            metadata={
                "identifier": resource["identifier"],
                "resource_type": "policy",
                "region": region,
                "method": "identity",
            },
        )

    def _convert_defined_tags_to_list(self, defined_tags):
        tag_list = []
        for namespace, keys in defined_tags.items():
            for key, value in keys.items():
                tag_list.append({
                    "namespace": namespace,
                    "key": key,
                    "value": value,
                })
        return tag_list

    def _merge_tags(self, defined_tags, new_value):
        tags = copy.deepcopy(defined_tags) if defined_tags else {}
        tags.setdefault(self.tag_namespace, {})
        tags[self.tag_namespace][self.tag_key] = new_value
        return tags

    def update_bucket(self, resource, region, value, tags):
        namespace = self.clients[region].object_storage_client.get_namespace().data
        name = resource.get("display_name") or resource.get("identifier_name")
        return self.clients[region].object_storage_client.update_bucket(
            namespace,
            name,
            UpdateBucketDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    def update_log_group(self, resource, region, value, tags):
        return self.clients[region].logging_management_client.update_log_group(
            resource["identifier"],
            UpdateLogGroupDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    def update_stack(self, resource, region, value, tags):
        return self.clients[region].resource_manager_client.update_stack(
            resource["identifier"],
            UpdateStackDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    def update_devops_project(self, resource, region, value, tags):
        return self.clients[region].devops_client.update_project(
            resource["identifier"],
            UpdateProjectDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    def update_devops_build_pipeline(self, resource, region, value, tags):
        return self.clients[region].devops_client.update_build_pipeline(
            resource["identifier"],
            UpdateBuildPipelineDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    def update_devops_deploy_pipeline(self, resource, region, value, tags):
        return self.clients[region].devops_client.update_deploy_pipeline(
            resource["identifier"],
            UpdateDeployPipelineDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    def update_devops_repository(self, resource, region, value, tags):
        return self.clients[region].devops_client.update_repository(
            resource["identifier"],
            UpdateRepositoryDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    def update_integration(self, resource, region, value, tags):
        return self.clients[region].integration_client.update_integration_instance(
            resource["identifier"],
            UpdateIntegrationInstanceDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    def update_oda(self, resource, region, value, tags):
        return self.clients[region].oda_client.update_oda_instance(
            resource["identifier"],
            UpdateOdaInstanceDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    def update_bastion(self, resource, region, value, tags):
        return self.clients[region].bastion_client.update_bastion(
            bastion_id=resource["identifier"],
            update_bastion_details=UpdateBastionDetails(
                defined_tags=self._merge_tags(tags, value)
            )
        ).status
    
    def update_event_rule(self, resource, region, value, tags):
        return self.clients[region].events_client.update_rule(
            rule_id=resource["identifier"],
            update_rule_details=UpdateRuleDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_alarm(self, resource, region, value, tags):
        return self.clients[region].monitoring_client.update_alarm(
            alarm_id=resource["identifier"],
            update_alarm_details=UpdateAlarmDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status
############ OSMH ######################################


    def update_managed_instance_group(self, resource, region, value, tags):
        return self.clients[region].managed_instance_group_client.update_managed_instance_group(
            managed_instance_group_id=resource["identifier"],
            update_managed_instance_group_details=UpdateManagedInstanceGroupDetails(
                defined_tags=self._merge_tags(tags, value)
        ),
        ).status


    def update_scheduled_job(self, resource, region, value, tags):
        return self.clients[region].scheduled_job_client.update_scheduled_job(
            scheduled_job_id=resource["identifier"],
            update_scheduled_job_details=UpdateScheduledJobDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_osms_software_source(self, resource, region, value, tags):
        return self.clients[region].software_source_client.update_software_source(
            software_source_id=resource["identifier"],
            update_software_source_details=UpdateSoftwareSourceDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status
    
######################################################################    
    
    def update_file_system(self, resource, region, value, tags):
        return self.clients[region].file_storage_client.update_file_system(
            file_system_id=resource["identifier"],
            update_file_system_details=UpdateFileSystemDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_mount_target(self, resource, region, value, tags):
        return self.clients[region].file_storage_client.update_mount_target(
            mount_target_id=resource["identifier"],
            update_mount_target_details=UpdateMountTargetDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status
    
    def update_email_sender(self, resource, region, value, tags):
        return self.clients[region].email_client.update_sender(
            sender_id=resource["identifier"],
            update_sender_details=UpdateSenderDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status

    def update_email_domain(self, resource, region, value, tags):
        return self.clients[region].email_client.update_email_domain(
            sender_id=resource["identifier"],
            update_sender_details=UpdateEmailDomainDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_topic(self, resource, region, value, tags):
        return self.clients[region].notification_control_plane_client.update_topic(
            topic_id=resource["identifier"],
            topic_attributes_details=TopicAttributesDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status
    
    def update_subscription(self, resource, region, value, tags):
        return self.clients[region].notification_data_plane_client.update_subscription(
            topic_id=resource["identifier"],
            topic_attributes_details=UpdateSubscriptionDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status
    
    def update_vault_secret(self, resource, region, value, tags):
        return self.clients[region].vaults_client.update_secret(
            secret_id=resource["identifier"],
            update_secret_details=UpdateSecretDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status
    
    def update_vault(self, resource, region, value, tags):
        return self.clients[region].kms_vault_client.update_vault(
            vault_id=resource["identifier"],
            update_vault_details=UpdateVaultDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status
    
    def update_key(self, resource, region, value, tags):
        return self.clients[region].kms_management_client.update_key(
            key_id=resource["identifier"],
            update_key_details=UpdateKeyDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status

###################### Database Resources ###############################################

    def update_autonomous_container_database(self, resource, region, value, tags):
        return self.clients[region].database_client.update_autonomous_container_database(
            autonomous_container_database_id=resource["identifier"],
            update_autonomous_container_database_details=UpdateAutonomousContainerDatabaseDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_autonomous_exadata_infrastructure(self, resource, region, value, tags):
        return self.clients[region].database_client.update_autonomous_exadata_infrastructure(
            autonomous_exadata_infrastructure_id=resource["identifier"],
            update_autonomous_exadata_infrastructure_details=UpdateAutonomousExadataInfrastructureDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_db_system(self, resource, region, value, tags):
        return self.clients[region].database_client.update_db_system(
            db_system_id=resource["identifier"],
            update_db_system_details=UpdateDbSystemDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_exadata_infrastructure(self, resource, region, value, tags):
        return self.clients[region].database_client.update_exadata_infrastructure(
            exadata_infrastructure_id=resource["identifier"],
            update_exadata_infrastructure_details=UpdateExadataInfrastructureDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status
    
    def update_backup_destination(self, resource, region, value, tags):
        return self.clients[region].database_client.update_backup_destination(
            backup_destination_id=resource["identifier"],
            update_backup_destination_details=UpdateBackupDestinationDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status
    
    def update_vm_cluster(self, resource, region, value, tags):
        return self.clients[region].database_client.update_vm_cluster(
            vm_cluster_id=resource["identifier"],
            update_vm_cluster_details=UpdateVmClusterDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status

###################### OCI CORE ###############################################

    def update_boot_volume_backup(self, resource, region, value, tags):
        return self.clients[region].blockstorage_client.update_boot_volume_backup(
            boot_volume_backup_id=resource["identifier"],
            update_boot_volume_backup_details=UpdateBootVolumeBackupDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_volume_backup(self, resource, region, value, tags):
        return self.clients[region].blockstorage_client.update_volume_backup(
            volume_backup_id=resource["identifier"],
            update_volume_backup_details=UpdateVolumeBackupDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_volume_group(self, resource, region, value, tags):
        return self.clients[region].blockstorage_client.update_volume_group(
            volume_group_id=resource["identifier"],
            update_volume_group_details=UpdateVolumeGroupDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_volume_group_backup(self, resource, region, value, tags):
        return self.clients[region].blockstorage_client.update_volume_group_backup(
            volume_group_backup_id=resource["identifier"],
            update_volume_group_backup_details=UpdateVolumeGroupBackupDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status    


    def update_vcn(self, resource, region, value, tags):
        return self.clients[region].virtual_network_client.update_vcn(
            vcn_id=resource["identifier"],
            update_vcn_details=UpdateVcnDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status

    def update_subnet(self, resource, region, value, tags):
        return self.clients[region].virtual_network_client.update_subnet(
            subnet_id=resource["identifier"],
            update_subnet_details=UpdateSubnetDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status    

    def update_internet_gateway(self, resource, region, value, tags):
        return self.clients[region].virtual_network_client.update_internet_gateway(
            ig_id=resource["identifier"],
            update_internet_gateway_details=UpdateInternetGatewayDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status
    
    def update_nat_gateway(self, resource, region, value, tags):
        return self.clients[region].virtual_network_client.update_nat_gateway(
            nat_gateway_id=resource["identifier"],
            update_nat_gateway_details=UpdateNatGatewayDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status

    def update_local_peering_gateway(self, resource, region, value, tags):
        return self.clients[region].virtual_network_client.update_local_peering_gateway(
            local_peering_gateway_id=resource["identifier"],
            update_local_peering_gateway_details=UpdateLocalPeeringGatewayDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_network_security_group(self, resource, region, value, tags):
        return self.clients[region].virtual_network_client.update_network_security_group(
            network_security_group_id=resource["identifier"],
            update_network_security_group_details=UpdateNetworkSecurityGroupDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_public_ip(self, resource, region, value, tags):
        return self.clients[region].virtual_network_client.update_public_ip(
            public_ip_id=resource["identifier"],
            update_public_ip_details=UpdatePublicIpDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_route_table(self, resource, region, value, tags):
        return self.clients[region].virtual_network_client.update_route_table(
            rt_id=resource["identifier"],
            update_route_table_details=UpdateRouteTableDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_security_list(self, resource, region, value, tags):
        return self.clients[region].virtual_network_client.update_security_list(
            security_list_id=resource["identifier"],
            update_security_list_details=UpdateSecurityListDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_service_gateway(self, resource, region, value, tags):
        return self.clients[region].virtual_network_client.update_service_gateway(
            service_gateway_id=resource["identifier"],
            update_service_gateway_details=UpdateServiceGatewayDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status

    def update_cross_connect(self, resource, region, value, tags):
        return self.clients[region].virtual_network_client.update_cross_connect(
            cross_connect_id=resource["identifier"],
            update_cross_connect_details=UpdateCrossConnectDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_cross_connect_group(self, resource, region, value, tags):
        return self.clients[region].virtual_network_client.update_cross_connect_group(
            cross_connect_group_id=resource["identifier"],
            update_cross_connect_group_details=UpdateCrossConnectGroupDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_ipsec_connection(self, resource, region, value, tags):
        return self.clients[region].virtual_network_client.update_ip_sec_connection(
            ipsc_id=resource["identifier"],
            update_ip_sec_connection_details=UpdateIPSecConnectionDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_remote_peering_connection(self, resource, region, value, tags):
        return self.clients[region].virtual_network_client.update_remote_peering_connection(
            remote_peering_connection_id=resource["identifier"],
            update_remote_peering_connection_details=UpdateRemotePeeringConnectionDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_virtual_circuit(self, resource, region, value, tags):
        return self.clients[region].virtual_network_client.update_virtual_circuit(
            virtual_circuit_id=resource["identifier"],
            update_virtual_circuit_details=UpdateVirtualCircuitDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status

    def update_cluster_network(self, resource, region, value, tags):
        return self.clients[region].compute_client.update_cluster_network(
            cluster_network_id=resource["identifier"],
            update_cluster_network_details=UpdateClusterNetworkDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_dedicated_vm_host(self, resource, region, value, tags):
        return self.clients[region].compute_client.update_dedicated_vm_host(
            dedicated_vm_host_id=resource["identifier"],
            update_dedicated_vm_host_details=UpdateDedicatedVmHostDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_image(self, resource, region, value, tags):
        return self.clients[region].compute_client.update_image(
            image_id=resource["identifier"],
            update_image_details=UpdateImageDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status    


    def update_instance_configuration(self, resource, region, value, tags):
        return self.clients[region].compute_management_client.update_instance_configuration(
            instance_configuration_id=resource["identifier"],
            update_instance_configuration_details=UpdateInstanceConfigurationDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status


    def update_instance_pool(self, resource, region, value, tags):
        return self.clients[region].compute_management_client.update_instance_pool(
            instance_pool_id=resource["identifier"],
            update_instance_pool_details=UpdateInstancePoolDetails(
                defined_tags=self._merge_tags(tags, value)
            ),
        ).status
