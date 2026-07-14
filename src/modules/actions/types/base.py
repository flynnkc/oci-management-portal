#!/usr/bin/python3.11

import copy
import re
from dataclasses import dataclass, field
from enum import StrEnum
from http import HTTPStatus
from typing import Optional

from ..result import Result


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


def normalize_resource_type(rtype: Optional[str]) -> str:
    return re.sub(r'[_\-\s]', '', (rtype or '').strip().lower()) if rtype else ""


class ActionKind(StrEnum):
    DELETE = "delete"
    EXTEND = "extend"


class ActionStrategy(StrEnum):
    # Strategies describe how a resource action is implemented. BaseResourceType
    # classes select one of these so Deleter/Extender do not need per-type
    # branching in their web-facing entry points.
    # Delete by calling Identity bulk_move_resources with a generic resource
    # descriptor. Resource types may override delete_bulk_resource() when OCI
    # needs resource-specific metadata in that descriptor.
    DELETE_BULK_MOVE = "delete_bulk_move"

    # Delete by calling a service client's change_*_compartment SDK method.
    # Resource types provide delete_client_attr and delete_method_name; Deleter
    # performs the common call shape.
    DELETE_SDK_MOVE = "delete_sdk_move"

    # Delete through resource-specific custom code. Resource types implement
    # force_delete() for APIs that cannot use bulk move or SDK compartment moves.
    DELETE_FORCE = "delete_force"

    # Extend by calling Identity bulk_edit_tags. Extender owns the common bulk
    # request; resource types choose this when no per-service update is needed.
    EXTEND_BULK_TAG = "extend_bulk_tag"

    # Extend by calling a service-specific update SDK method. Resource types
    # either provide SDK metadata for Extender's common call shape or override
    # extend_sdk_tag() for unusual payloads such as Object Storage buckets.
    EXTEND_SDK_TAG = "extend_sdk_tag"

    # Extend through identity-domain or identity-service-specific code. Resource
    # types implement extend() when tag updates require SCIM/domain/classic IAM
    # behavior instead of ordinary tag APIs.
    EXTEND_IDENTITY = "extend_identity"


@dataclass(frozen=True)
class ResourceActionSpec:
    # Lightweight metadata used by the UI and support checks. These specs are
    # derived from BaseResourceType classes; contributors should normally add or edit
    # a BaseResourceType under actions/types/ rather than instantiate this directly.
    resource_type: str
    action: ActionKind
    strategy: ActionStrategy
    display_name: str | None = None
    aliases: tuple[str, ...] = field(default_factory=tuple)
    client_attr: str | None = None
    method_name: str | None = None
    requires_home_region: bool = False
    supports_work_request: bool = True

    @property
    def label(self) -> str:
        return self.display_name or self.resource_type


class ResourceActionRegistry:
    # Internal accumulator used while discovering BaseResourceType subclasses from
    # ACTION_SPEC_MODULES. It keeps both the executable classes and the derived
    # metadata specs in sync.
    def __init__(self):
        self._specs: list[ResourceActionSpec] = []
        self._resource_types: list[type["BaseResourceType"]] = []

    def specs(self) -> tuple[ResourceActionSpec, ...]:
        return tuple(self._specs)

    def register_type(self, resource_type: type["BaseResourceType"]) -> None:
        self._resource_types.append(resource_type)
        self._specs.extend(resource_type.action_specs())

    def resource_types(self) -> tuple[type["BaseResourceType"], ...]:
        return tuple(self._resource_types)


class BaseResourceType:
    # Extension point for OCI resource support.
    #
    # Add one module per supported resource under actions/types/ and define one
    # BaseResourceType subclass in that module. Deleter and Extender discover these
    # classes at startup, filter them by action, and delegate execution to the
    # class. Simple resources only declare strategy metadata; unusual resources
    # can override delete(), force_delete(), or extend() for custom behavior.
    resource_type: str = ""
    display_name: str | None = None
    aliases: tuple[str, ...] = ()

    delete_strategy: ActionStrategy | None = None
    delete_client_attr: str | None = None
    delete_method_name: str | None = None

    extend_strategy: ActionStrategy | None = None
    extend_client_attr: str | None = None
    extend_method_name: str | None = None
    extend_identifier_param: str | None = None
    extend_details_param: str | None = None
    extend_details_cls = None

    @classmethod
    def label(cls) -> str:
        return cls.display_name or cls.resource_type

    @classmethod
    def action_specs(cls) -> tuple[ResourceActionSpec, ...]:
        # Convert the type class into action-specific specs for supported
        # resources pages, card enrichment, CSV exports, and lookup maps.
        specs: list[ResourceActionSpec] = []
        common = {
            "resource_type": cls.resource_type,
            "display_name": cls.display_name,
            "aliases": cls.aliases,
        }
        if cls.delete_strategy:
            specs.append(
                ResourceActionSpec(
                    action=ActionKind.DELETE,
                    strategy=cls.delete_strategy,
                    client_attr=cls.delete_client_attr,
                    method_name=cls.delete_method_name,
                    **common,
                )
            )
        if cls.extend_strategy:
            specs.append(
                ResourceActionSpec(
                    action=ActionKind.EXTEND,
                    strategy=cls.extend_strategy,
                    **common,
                )
            )
        return tuple(specs)

    @classmethod
    def normalized_names(cls) -> tuple[str, ...]:
        return tuple(
            normalize_resource_type(name)
            for name in (cls.resource_type, *cls.aliases)
            if name
        )

    def _region(self, action, resource, explicit_region: str | None = None) -> str | None:
        if explicit_region:
            return explicit_region

        norm = normalize_resource_type(resource.get("resource_type"))
        if norm in {
            "user",
            "group",
            "dynamicgroup",
            "dynamicresourcegroup",
            "confidentialapplication",
            "app",
            "policy",
        }:
            return action._get_tenancy_home_region_name()

        region_hint = resource.get("region") or resource.get("home_region")
        if region_hint:
            return region_hint

        return self._derive_region_from_ocid(resource.get("identifier"))

    @staticmethod
    def _derive_region_from_ocid(ocid: str | None):
        if not ocid:
            return None
        match = re.search(r"\.oc1\.([a-z]+)\.", ocid)
        if match:
            return OCID_REGION_CODES.get(match.group(1))
        return None

    def force_delete(self, deleter, resource) -> Result:
        rtype = resource.get("resource_type")
        ocid = resource.get("identifier")
        return Result(
            HTTPStatus.NOT_IMPLEMENTED,
            message=f"No force delete implementation for {rtype}",
            metadata={"resource_type": rtype, "identifier": ocid},
        )

    def delete(self, deleter, resource, region, target) -> Result:
        rtype = resource.get("resource_type")
        ocid = resource.get("identifier")
        return Result(
            HTTPStatus.NOT_IMPLEMENTED,
            message=f"No delete implementation for {rtype}",
            metadata={"resource_type": rtype, "identifier": ocid},
        )

    def delete_bulk_resource(self, deleter, resource, region) -> dict:
        return {
            "entityType": resource["resource_type"],
            "identifier": resource["identifier"],
        }

    def extend(self, extender, resource, region, new_value, defined_tags) -> Result:
        rtype = resource.get("resource_type")
        ocid = resource.get("identifier")
        return Result(
            HTTPStatus.NOT_IMPLEMENTED,
            message=f"No extender implementation for {rtype}",
            metadata={"identifier": ocid, "resource_type": rtype},
        )

    def _merge_tags(self, extender, defined_tags, new_value):
        tags = copy.deepcopy(defined_tags) if defined_tags else {}
        tags.setdefault(extender.tag_namespace, {})
        tags[extender.tag_namespace][extender.tag_key] = new_value
        return tags

    def extend_sdk_tag(self, extender, resource, region, new_value, defined_tags):
        raise NotImplementedError(
            f"No custom SDK tag update configured for {self.resource_type}"
        )
