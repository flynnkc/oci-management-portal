#!/usr/bin/python3.11

import logging
import copy
import re
from datetime import datetime, timedelta
from http import HTTPStatus

from oci.core.models import (
    UpdateInstanceDetails,
    UpdateVolumeDetails,
    UpdateBootVolumeDetails,
)
from oci.object_storage.models import UpdateBucketDetails
from oci.database.models import UpdateAutonomousDatabaseDetails
from oci.analytics.models import UpdateAnalyticsInstanceDetails
from oci.integration.models import UpdateIntegrationInstanceDetails
from oci.oda.models import UpdateOdaInstanceDetails
from oci.logging.models import UpdateLogGroupDetails
from oci.resource_manager.models import UpdateStackDetails
from oci.devops.models import (
    UpdateProjectDetails,
    UpdateBuildPipelineDetails,
    UpdateDeployPipelineDetails,
    UpdateRepositoryDetails,
)

from .client_bundle import ClientBundle
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


def derive_region_from_ocid(ocid: str) -> str | None:
    match = re.search(r"\.oc1\.([a-z]+)\.", ocid)
    if match:
        return OCID_REGION_CODES.get(match.group(1))
    return None


class Extender:
    """
    Extends expiry tag on OCI resources by 30 days.
    """

    def __init__(
        self,
        config,
        signer,
        tag_namespace: str,
        tag_key: str,
        handler=logging.StreamHandler(),
        log_level=logging.INFO,
        regions: list[str] | None = None,
    ):
        self.logger = log_factory(__name__, log_level, handler)
        self.config = config
        self.signer = signer
        self.tag_namespace = tag_namespace
        self.tag_key = tag_key

        self.clients: dict[str, ClientBundle] = self.create_clients(regions)

        # Supported resource types
        self.update_tag_tree = {
            # Core
            "Instance": self.update_instance,
            "Volume": self.update_volume,
            "BootVolume": self.update_boot_volume,

            # Database / Analytics
            "AutonomousDatabase": self.update_autonomous_db,
            "AnalyticsInstance": self.update_analytics,

            # Integration / ODA
            "IntegrationInstance": self.update_integration,
            "OdaInstance": self.update_oda,

            # DevOps
            "DevOpsProject": self.update_devops_project,
            "DevOpsBuildPipeline": self.update_devops_build_pipeline,
            "DevOpsDeployPipeline": self.update_devops_deploy_pipeline,
            "DevOpsRepository": self.update_devops_repository,

            # Observability
            "LogGroup": self.update_log_group,

            # Resource Manager
            "ResourceManagerStack": self.update_stack,
            "OrmStack": self.update_stack,

            # Object Storage
            "ObjectStorageBucket": self.update_bucket,
            "Bucket": self.update_bucket,
        }

        self.logger.info("Extender initialized")

    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    def extend(self, resource: dict) -> int:
        identifier = resource.get("identifier")
        resource_type = resource.get("resource_type")
        defined_tags = resource.get("defined_tags", {})

        region = self._get_region(resource)
        if not region:
            self.logger.error("Unable to determine region")
            return HTTPStatus.BAD_REQUEST

        current_value = defined_tags.get(self.tag_namespace, {}).get(self.tag_key)
        base_date = (
            datetime.strptime(current_value, "%Y-%m-%d").date()
            if current_value else datetime.utcnow().date()
        )
        new_value = (base_date + timedelta(days=30)).strftime("%Y-%m-%d")

        self.logger.info(
            f"Extending {resource_type} {identifier}: {current_value} → {new_value}"
        )

        updater = self.update_tag_tree.get(resource_type)
        if not updater:
            self.logger.warning(f"{resource_type} not supported for extend")
            return HTTPStatus.NOT_IMPLEMENTED

        return updater(identifier, region, new_value, defined_tags)

    # ------------------------------------------------------------------
    def _merge_tags(self, defined_tags, new_value):
        tags = copy.deepcopy(defined_tags) if defined_tags else {}
        tags.setdefault(self.tag_namespace, {})
        tags[self.tag_namespace][self.tag_key] = new_value
        return tags

    # ---- Core ----
    def update_instance(self, ocid, region, value, tags):
        return self.clients[region].compute_client.update_instance(
            ocid,
            UpdateInstanceDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    def update_volume(self, ocid, region, value, tags):
        return self.clients[region].blockstorage_client.update_volume(
            ocid,
            UpdateVolumeDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    def update_boot_volume(self, ocid, region, value, tags):
        return self.clients[region].blockstorage_client.update_boot_volume(
            ocid,
            UpdateBootVolumeDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    # ---- Database / Analytics ----
    def update_autonomous_db(self, ocid, region, value, tags):
        return self.clients[region].database_client.update_autonomous_database(
            ocid,
            UpdateAutonomousDatabaseDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    def update_analytics(self, ocid, region, value, tags):
        return self.clients[region].analytics_client.update_analytics_instance(
            ocid,
            UpdateAnalyticsInstanceDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    # ---- Integration / ODA ----
    def update_integration(self, ocid, region, value, tags):
        return self.clients[region].integration_client.update_integration_instance(
            ocid,
            UpdateIntegrationInstanceDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    def update_oda(self, ocid, region, value, tags):
        return self.clients[region].oda_client.update_oda_instance(
            ocid,
            UpdateOdaInstanceDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    # ---- DevOps ----
    def update_devops_project(self, ocid, region, value, tags):
        return self.clients[region].devops_client.update_project(
            ocid,
            UpdateProjectDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    def update_devops_build_pipeline(self, ocid, region, value, tags):
        return self.clients[region].devops_client.update_build_pipeline(
            ocid,
            UpdateBuildPipelineDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    def update_devops_deploy_pipeline(self, ocid, region, value, tags):
        return self.clients[region].devops_client.update_deploy_pipeline(
            ocid,
            UpdateDeployPipelineDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    def update_devops_repository(self, ocid, region, value, tags):
        return self.clients[region].devops_client.update_repository(
            ocid,
            UpdateRepositoryDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    # ---- Logging ----
    def update_log_group(self, ocid, region, value, tags):
        return self.clients[region].logging_management_client.update_log_group(
            ocid,
            UpdateLogGroupDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    # ---- Resource Manager ----
    def update_stack(self, ocid, region, value, tags):
        return self.clients[region].resource_manager_client.update_stack(
            ocid,
            UpdateStackDetails(defined_tags=self._merge_tags(tags, value))
        ).status

    # ---- Object Storage ----
    def update_bucket(self, name, region, value, tags):
        namespace = self.clients[region].object_storage_client.get_namespace().data
        return self.clients[region].object_storage_client.update_bucket(
            namespace,
            name,
            UpdateBucketDetails(defined_tags=self._merge_tags(tags, value))
        ).status

