#!/usr/bin/python3.11

import logging
from http import HTTPStatus
from typing import List, Dict

from oci.identity.models import BulkMoveResourcesDetails
from .client_bundle import ClientBundle
from ..utils import log_factory

# TEMPORARY: hardcoded quarantine compartment
QUARANTINE_COMPARTMENT_OCID = (
    "ocid1.compartment.oc1..aaaaaaaaeiajbz76hewnwwlqa5o2dpidbg4wm3jghv7a3euoao44zir3shgq"
)


class Deleter:
    """
    Deleter performs MOVE (quarantine) using OCI Identity bulkMoveResources.
    DELETE is intentionally not implemented.
    """

    def __init__(
        self,
        config,
        signer,
        handler=logging.StreamHandler(),
        log_level=logging.INFO,
        regions: list[str] | None = None,
    ):
        self.logger = log_factory(__name__, log_level, handler)
        self.config = config
        self.signer = signer
        self.clients: dict[str, ClientBundle] = self.create_clients(regions)

        self.logger.info("Deleter initialized (bulk move mode)")

    # =========================
    # CLIENT CREATION
    # =========================
    def create_clients(self, regions: list[str] | None) -> dict[str, ClientBundle]:
        clients = {}

        if not regions:
            region = self.config["region"]
            clients[region] = ClientBundle(self.config, self.signer)
            self.logger.debug("Created client bundle for region %s", region)
        else:
            for region in regions:
                self.config["region"] = region
                self.signer.region = region
                clients[region] = ClientBundle(self.config, self.signer)
                self.logger.debug("Created client bundle for region %s", region)

        return clients

    # =========================
    # ENTITY TYPE RESOLUTION
    # =========================
    def _resolve_entity_type(self, resource: Dict) -> str | None:
        entity_type = resource.get("resource_type")

        self.logger.debug(
            "Resolving entityType: ocid=%s resource_type=%s",
            resource.get("identifier"),
            entity_type,
        )

        return entity_type

    # =========================
    # BULK MOVE FUNCTION
    # =========================
    def move(self, resources: List[Dict], **kwargs) -> int:
        """
        Perform bulk move using IdentityClient.bulk_move_resources.

        Expected resource dict format:
        {
            "identifier": "<ocid>",
            "resource_type": "<EntityType>",
            "compartment_id": "<source_compartment_ocid>"
        }
        """
        region = kwargs.get("region")
        target_compartment_id = kwargs.get(
            "target_compartment_id", QUARANTINE_COMPARTMENT_OCID
        )

        if not region:
            self.logger.error("Missing region for bulk move")
            return HTTPStatus.BAD_REQUEST

        if region not in self.clients:
            self.logger.error("No client bundle found for region %s", region)
            return HTTPStatus.BAD_REQUEST

        if not resources:
            self.logger.error("No resources supplied for bulk move")
            return HTTPStatus.BAD_REQUEST

        valid_resources = []
        source_compartment_id = None

        for r in resources:
            ocid = r.get("identifier")
            compartment_id = r.get("compartment_id")
            entity_type = self._resolve_entity_type(r)

            self.logger.debug(
                "Evaluating resource: ocid=%s entityType=%s compartment=%s",
                ocid,
                entity_type,
                compartment_id,
            )

            if not ocid or not entity_type or not compartment_id:
                self.logger.warning(
                    "Skipping resource due to missing fields: ocid=%s entityType=%s compartment=%s",
                    ocid,
                    entity_type,
                    compartment_id,
                )
                continue

            if source_compartment_id is None:
                source_compartment_id = compartment_id
                self.logger.debug(
                    "Using source compartment %s for bulk move",
                    source_compartment_id,
                )
            elif compartment_id != source_compartment_id:
                self.logger.warning(
                    "Skipping resource %s due to mismatched source compartment (%s != %s)",
                    ocid,
                    compartment_id,
                    source_compartment_id,
                )
                continue

            valid_resources.append(
                {
                    "identifier": ocid,
                    "entityType": entity_type,
                }
            )

        if not valid_resources:
            self.logger.error("No valid resources to move after validation")
            return HTTPStatus.BAD_REQUEST

        self.logger.info(
            "Preparing bulk move: count=%d source=%s target=%s region=%s",
            len(valid_resources),
            source_compartment_id,
            target_compartment_id,
            region,
        )

        details = BulkMoveResourcesDetails(
            target_compartment_id=target_compartment_id,
            resources=valid_resources,
        )

        try:
            client = self.clients[region].identity_client

            self.logger.debug(
                "Invoking bulkMoveResources: compartment=%s payload=%s",
                source_compartment_id,
                valid_resources,
            )

            response = client.bulk_move_resources(
                source_compartment_id,
                details,
            )

            self.logger.info(
                "Bulk move request accepted: status=%s opc-request-id=%s",
                response.status,
                response.headers.get("opc-request-id"),
            )

            return response.status

        except Exception as e:
            self.logger.exception("Bulk move failed")
            return HTTPStatus.INTERNAL_SERVER_ERROR

