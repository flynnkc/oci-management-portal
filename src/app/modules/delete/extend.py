#!/usr/bin/python3.11

import logging
import copy
import re
from datetime import datetime, timedelta
from http import HTTPStatus

from oci.exceptions import ServiceError
from oci.identity.models import (
    BulkEditTagsDetails,
    BulkEditOperationDetails,
    BulkEditResource,
)

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
from ..utils import log_factory


# Bulk tag edit supported by OCI
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

# OCI Regions: Need to add more !!
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


def derive_region_from_ocid(ocid: str) -> str | None:
    match = re.search(r"\.oc1\.([a-z]+)\.", ocid)
    if match:
        return OCID_REGION_CODES.get(match.group(1))
    return None


class Extender:
    """
    Extend expiry tag.

    Rules:
    - Use BULK only where OCI truly supports it
    - Use SDK where bulk is not supported
    - Everything else naturally becomes NOT IMPLEMENTED
    """

    def __init__(
        self,
        config,
        signer,
        tag_namespace: str,
        tag_key: str,
        handler=logging.StreamHandler(),
        log_level=logging.INFO,
        regions=None,
    ):
        self.logger = log_factory(__name__, log_level, handler)
        self.config = config
        self.signer = signer
        self.tag_namespace = tag_namespace
        self.tag_key = tag_key

        self.clients = self.create_clients(regions)

        # SDK extend implementations
        self.update_tag_tree = {
            "Bucket": self.update_bucket,
            "ObjectStorageBucket": self.update_bucket,

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

        self.logger.info("Extender initialized")

    # -------------------------
    # Client creation
    # -------------------------
    def create_clients(self, regions):
        clients = {}
        if regions:
            for region in regions:
                self.config["region"] = region
                self.signer.region = region
                clients[region] = ClientBundle(self.config, self.signer)
        return clients

    def _get_region(self, resource):
        ocid = resource.get("identifier")
        region = derive_region_from_ocid(ocid)
        if region and region not in self.clients:
            self.config["region"] = region
            self.signer.region = region
            self.clients[region] = ClientBundle(self.config, self.signer)
        return region


    # -------------------------
    # Specifc SDK Logic 
    # -------------------------
    def extend(self, resource: dict) -> int:
        ocid = resource.get("identifier")
        rtype = resource.get("resource_type")
        defined_tags = resource.get("defined_tags", {})
        compartment_id = resource.get("compartment_id")

        region = self._get_region(resource)
        if not region:
            self.logger.error("Unable to determine region for %s", ocid)
            return HTTPStatus.BAD_REQUEST

        current = defined_tags.get(self.tag_namespace, {}).get(self.tag_key)
        base = (
            datetime.strptime(current, "%Y-%m-%d").date()
            if current else datetime.utcnow().date()
        )
        new_value = (base + timedelta(days=30)).strftime("%Y-%m-%d")

        self.logger.info(
            "Extending %s %s: %s → %s",
            rtype, ocid, current, new_value
        )

        # -------- BULK path --------
        if rtype in BULK_EXTEND_SUPPORTED_TYPES:
            if self._try_bulk_extend(resource, region, new_value):
                self.logger.info(
                    "Bulk extend succeeded for %s (%s)",
                    rtype, ocid
                )
                return HTTPStatus.OK

            self.logger.error(
                "Bulk supported resource failed via bulk extend: %s (%s)",
                rtype, ocid
            )
            return HTTPStatus.NOT_IMPLEMENTED

        # -------- SDK path --------
        updater = self.update_tag_tree.get(rtype)
        if not updater:
            self.logger.error(
                "No extend implementation for %s (%s)",
                rtype, ocid
            )
            return HTTPStatus.NOT_IMPLEMENTED

        try:
            return updater(resource, region, new_value, defined_tags)
        except Exception:
            self.logger.exception(
                "SDK extend failed for %s (%s)",
                rtype, ocid
            )
            return HTTPStatus.INTERNAL_SERVER_ERROR


    def _try_bulk_extend(self, resource, region, new_value) -> bool:
        ocid = resource.get("identifier")
        rtype = resource.get("resource_type")
        compartment_id = resource.get("compartment_id")

        if not compartment_id:
            self.logger.error(
                "Missing compartment_id for bulk extend %s (%s)",
                rtype, ocid
            )
            return False

        try:
            bulk_resource = BulkEditResource(
                id=ocid,
                resource_type=rtype,
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
                compartment_id=compartment_id,
                resources=[bulk_resource],
                bulk_edit_operations=[bulk_operation],
            )

            self.clients[region].identity_client.bulk_edit_tags(
                bulk_edit_tags_details=details
            )
            return True

        except ServiceError as e:
            self.logger.info(
                "Bulk extend rejected by OCI for %s (%s): %s",
                rtype, ocid, e.message
            )
            return False

        except Exception:
            self.logger.exception(
                "Bulk extend crashed for %s (%s)",
                rtype, ocid
            )
            return False


    def _merge_tags(self, defined_tags, new_value):
        tags = copy.deepcopy(defined_tags) if defined_tags else {}
        tags.setdefault(self.tag_namespace, {})
        tags[self.tag_namespace][self.tag_key] = new_value
        return tags

    # ---------------- SDK implementations ----------------

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