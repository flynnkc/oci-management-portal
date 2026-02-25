#!/usr/bin/python3.11

import logging
import copy
import re
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any, Optional, Tuple

import oci
from oci.exceptions import ServiceError

# Bulk tag edit
from oci.identity.models import (
    BulkEditTagsDetails,
    BulkEditOperationDetails,
    BulkEditResource,
)

# Identity Domain
from oci.identity_domains import IdentityDomainsClient
from oci.identity_domains.models import PatchOp, Operations

# SDK models
from oci.object_storage.models import UpdateBucketDetails
from oci.logging.models import UpdateLogGroupDetails
from oci.resource_manager.models import UpdateStackDetails
from oci.devops.models import (
    UpdateProjectDetails,
    UpdateBuildPipelineDetails,
    UpdateDeployPipelineDetails,
    UpdateRepositoryDetails,
)
from oci.integration.models import UpdateIntegrationInstanceDetails
from oci.oda.models import UpdateOdaInstanceDetails
from oci.bastion.models import UpdateBastionDetails

from .client_bundle import ClientBundle
from .result import Result
from ..utils import log_factory


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

    IDENTITY_TYPES = {
        "user",
        "group",
        "dynamicresourcegroup",
        "confidentialapplication",
        "app",
    }

    CLASSIC_IDENTITY_TYPES = {"policy"}

    def __init__(
        self,
        config,
        signer,
        tag_namespace,
        tag_key,
        extend_period=timedelta(days=30),
        handler=logging.StreamHandler(),
        log_level=logging.INFO,
        regions=None,
    ):
        self.logger = log_factory(__name__, log_level, handler)
        self.config = config
        self.signer = signer
        self.tag_namespace = tag_namespace
        self.tag_key = tag_key
        self.extend_period = extend_period

        self.clients = self._create_clients(regions)
        self._domain_client_cache = {}
        self._home_region = None

        self.update_tag_tree = {
            "Bucket": self.update_bucket,
            "DevOpsProject": self.update_devops_project,
            "DevOpsBuildPipeline": self.update_devops_build_pipeline,
            "DevOpsDeployPipeline": self.update_devops_deploy_pipeline,
            "DevOpsRepository": self.update_devops_repository,
            "LogGroup": self.update_log_group,
            "ResourceManagerStack": self.update_stack,
            "OrmStack": self.update_stack,
            "IntegrationInstance": self.update_integration,
            "OdaInstance": self.update_oda,
            "Bastion": self.update_bastion,
        }

        self.logger.info("Unified Extender initialized")

    # ============================================================
    # REGION HANDLING
    # ============================================================

    def _normalize_resource_type(self, rtype: Optional[str]) -> str:
        return re.sub(r'[_\-\s]', '', (rtype or '').strip().lower())

    def _get_tenancy_home_region_name(self):
        if self._home_region:
            return self._home_region

        identity_client = oci.identity.IdentityClient(self.config, signer=self.signer)
        tenancy_id = self.config["tenancy"]
        tenancy = identity_client.get_tenancy(tenancy_id).data
        home_region_key = tenancy.home_region_key
        regions = identity_client.list_region_subscriptions(tenancy_id).data

        for reg in regions:
            if reg.region_key == home_region_key:
                self._home_region = reg.region_name
                return self._home_region

        raise Exception(f"Unable to determine home region name for key {home_region_key}")

    def _get_region(self, resource):
        ocid = resource.get("identifier")
        rtype = self._normalize_resource_type(resource.get("resource_type"))

        identity_types = {
            "user",
            "group",
            "dynamicresourcegroup",
            "confidentialapplication",
            "policy",
        }

        region_hint = resource.get("region") or resource.get("home_region")

        if rtype in identity_types:
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
        clients = {}
        original_region = self.config.get("region")
        original_signer_region = getattr(self.signer, "region", None)

        if regions:
            if self.signer is None:
                raise ValueError("Signer is required when creating clients for multiple regions")
            for region in regions:
                clients[region] = self._build_client_for_region(region)
        elif original_region:
            clients[original_region] = self._build_client_for_region(original_region)

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
        signer = self.signer
        original_signer_region = getattr(signer, "region", None)
        if signer is not None:
            signer.region = region
        bundle = ClientBundle(region_config, signer)
        if signer is not None and original_signer_region is not None:
            signer.region = original_signer_region
        return bundle

    # ============================================================
    # IDENTITY DOMAIN RESOLUTION (MULTI DOMAIN SAFE)
    # ============================================================

    def _get_identity_domains_client(self, resource):
        resource_ocid = resource["identifier"]
        rtype = self._normalize_resource_type(resource.get("resource_type"))
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
            try:
                domain_region = domain.home_region
                domain_endpoint = domain.url

                if not domain_region or not domain_endpoint:
                    continue

                self.config["region"] = domain_region
                self.signer.region = domain_region

                client = IdentityDomainsClient(
                    self.config,
                    service_endpoint=domain_endpoint,
                    signer=self.signer,
                )

                if rtype == "user":
                    client.get_user(user_id=resource_ocid)

                elif rtype == "group":
                    client.get_group(group_id=resource_ocid)

                elif rtype == "dynamicresourcegroup":
                    client.get_dynamic_resource_group(
                        dynamic_resource_group_id=resource_ocid
                    )

                elif rtype in ("confidentialapplication", "app"):
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

        raise Exception(f"Unable to determine Identity Domain for {resource_ocid}")

    # ============================================================
    # MAIN EXTEND ENTRY
    # ============================================================
    def extend(self, resource: dict) -> Result:
        ocid = resource.get("identifier")
        rtype = resource.get("resource_type", "")
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

        # ---------------- IDENTITY DOMAIN ----------------
        if rtype in self.IDENTITY_TYPES:
            return self._update_identity_resource(resource, rtype, new_value)

        # -------- BULK --------
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
        
        # ---------------- CLASSIC IDENTITY ----------------
        if rtype in self.CLASSIC_IDENTITY_TYPES:
            return self._update_policy_classic(resource, region, new_value)

        # -------- SDK path --------
        updater = self.update_tag_tree.get(rtype)
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

    # ============================================================
    # IDENTITY PATCH
    # ============================================================
    def _update_identity_resource(self, resource, rtype, new_value):
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

        if rtype == "user":
            response = client.patch_user(user_id=resource_ocid, patch_op=patch)

        elif rtype == "group":
            response = client.patch_group(group_id=resource_ocid, patch_op=patch)

        elif rtype == "dynamicresourcegroup":
            response = client.patch_dynamic_resource_group(
                dynamic_resource_group_id=resource_ocid,
                patch_op=patch,
            )

        elif rtype in ("confidentialapplication", "app"):
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
                "resource_type": rtype,
                "method": "identity",
            },
        )


    # ============================================================
    # CLASSIC POLICY UPDATE
    # ============================================================

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
    # ============================================================
    # TAG MERGE
    # ============================================================

    def _merge_tags(self, defined_tags, new_value):
        tags = copy.deepcopy(defined_tags) if defined_tags else {}
        tags.setdefault(self.tag_namespace, {})
        tags[self.tag_namespace][self.tag_key] = new_value
        return tags

    # ============================================================
    # SDK METHODS
    # ============================================================

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