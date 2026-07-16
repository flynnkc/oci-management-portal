#!/usr/bin/python3.11
from http import HTTPStatus

from oci.identity.models import MoveCompartmentDetails, UpdateCompartmentDetails

from .base import ActionStrategy, BaseResourceType
from ..result import Result


class CompartmentResource(BaseResourceType):
    resource_type = 'Compartment'
    aliases = ('compartment',)
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    extend_strategy = ActionStrategy.EXTEND_IDENTITY

    def _region(self, action, resource, explicit_region: str | None = None) -> str | None:
        return explicit_region or resource.get("region") or action._get_tenancy_home_region_name()

    def delete(self, deleter, resource, region, target) -> Result:
        home_region, clients = deleter._get_home_region_client_bundle()
        response = clients.identity_client.move_compartment(
            compartment_id=resource["identifier"],
            move_compartment_details=MoveCompartmentDetails(
                target_compartment_id=target,
            ),
        )
        status = getattr(response, "status", HTTPStatus.OK)
        headers = getattr(response, "headers", {}) or {}
        return Result(
            status=status,
            work_request=headers.get("opc-work-request-id"),
            metadata={
                "method": "sdk",
                "resource_type": self.resource_type,
                "identifier": resource["identifier"],
                "region": home_region,
            },
        )

    def extend(self, extender, resource, region, new_value, defined_tags) -> Result:
        home_region, clients = extender._get_home_region_client_bundle()
        response = clients.identity_client.update_compartment(
            compartment_id=resource["identifier"],
            update_compartment_details=UpdateCompartmentDetails(
                defined_tags=self._merge_tags(extender, defined_tags, new_value),
                freeform_tags=(
                    resource.get("freeform_tags")
                    or resource.get("freeformTags")
                    or {}
                ),
            ),
        )
        status = getattr(response, "status", HTTPStatus.OK)
        return Result(
            status=status,
            message=f"Expiry extended to {new_value}",
            metadata={
                "identifier": resource["identifier"],
                "resource_type": self.resource_type,
                "region": home_region,
                "method": "identity",
            },
        )
