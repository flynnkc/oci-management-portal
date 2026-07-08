#!/usr/bin/python3.11

import re
from dataclasses import dataclass, field
from enum import StrEnum
from http import HTTPStatus
from typing import Optional

from ..result import Result


def normalize_resource_type(rtype: Optional[str]) -> str:
    return re.sub(r'[_\-\s]', '', (rtype or '').strip().lower()) if rtype else ""


class ActionKind(StrEnum):
    DELETE = "delete"
    EXTEND = "extend"


class ActionStrategy(StrEnum):
    # Strategies describe how a resource action is implemented. BaseResourceType
    # classes select one of these so Deleter/Extender do not need per-type
    # branching in their web-facing entry points.
    DELETE_BULK_MOVE = "delete_bulk_move"
    DELETE_SDK_MOVE = "delete_sdk_move"
    DELETE_FORCE = "delete_force"
    EXTEND_BULK_TAG = "extend_bulk_tag"
    EXTEND_SDK_TAG = "extend_sdk_tag"
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
    # Optional name of a method on Extender to use for SDK tag updates.
    extend_handler: str | None = None

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

    def delete(self, deleter, resource, region, target) -> Result:
        # Default delete dispatcher for common strategies. Override this method
        # in a resource type class when OCI needs resource-specific payloads or
        # pre/post work that does not fit one of these generic paths.
        resource = {**resource, "resource_type": self.resource_type}
        rtype = self.resource_type
        ocid = resource.get("identifier")
        metadata = {
            "resource_type": rtype,
            "identifier": ocid,
        }
        last_error: Result | None = None

        if self.delete_strategy == ActionStrategy.DELETE_FORCE:
            try:
                result = self.force_delete(deleter, resource)
                deleter.logger.info("Force delete succeeded for %s (%s)", rtype, ocid)
                return result
            except Exception as exc:
                deleter.logger.exception("Force delete failed for %s (%s)", rtype, ocid)
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
        if region not in deleter.clients:
            return Result(
                HTTPStatus.NOT_FOUND,
                message=f"No client configured for region {region}",
                metadata={"resource_type": rtype, "identifier": ocid, "region": region},
            )

        metadata["region"] = region

        if self.delete_strategy == ActionStrategy.DELETE_BULK_MOVE:
            bulk_result, bulk_success = deleter._try_bulk_one(resource, region, target)
            if bulk_success and bulk_result:
                deleter.logger.info("Bulk move succeeded for %s (%s)", rtype, ocid)
                bulk_result.metadata.update({"method": "bulk", **metadata})
                return bulk_result

            if bulk_result:
                last_error = bulk_result
            deleter.logger.error(
                "Bulk supported resource failed via bulk: %s (%s)", rtype, ocid
            )

        if self.delete_strategy == ActionStrategy.DELETE_SDK_MOVE:
            if self.delete_client_attr and self.delete_method_name:
                try:
                    response = deleter._move_with_sdk_spec(
                        (self.delete_client_attr, self.delete_method_name),
                        identifier=ocid,
                        region=region,
                        target_compartment_id=target,
                    )
                    deleter.logger.info("SDK move succeeded for %s (%s)", rtype, ocid)
                    status = getattr(response, "status", HTTPStatus.OK)
                    headers = getattr(response, "headers", {}) or {}
                    work_request = headers.get("opc-work-request-id")
                    return Result(
                        status=status,
                        work_request=work_request,
                        metadata={"method": "sdk", **metadata},
                    )
                except Exception:
                    deleter.logger.exception("SDK move failed for %s (%s)", rtype, ocid)
                    last_error = Result(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        message=f"SDK move failed for {rtype} {ocid}",
                        metadata={"method": "sdk", **metadata},
                    )

        deleter.logger.error("Delete failed after all attempts for %s (%s)", rtype, ocid)
        return last_error or Result(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            message=f"Delete failed after all attempts for {rtype} {ocid}",
            metadata=metadata,
        )

    def force_delete(self, deleter, resource) -> Result:
        rtype = resource.get("resource_type")
        ocid = resource.get("identifier")
        return Result(
            HTTPStatus.NOT_IMPLEMENTED,
            message=f"No force delete implementation for {rtype}",
            metadata={"resource_type": rtype, "identifier": ocid},
        )

    def extend(self, extender, resource, region, new_value, defined_tags) -> Result:
        # Default extend dispatcher for common tag-extension strategies. Override
        # this in the resource type class when a resource needs custom tag merge
        # logic or a dedicated SDK call shape.
        resource = {**resource, "resource_type": self.resource_type}
        ocid = resource.get("identifier")
        rtype = self.resource_type
        norm = extender.normalize_resource_type(rtype)

        if self.extend_strategy == ActionStrategy.EXTEND_IDENTITY:
            if norm in {"user", "group", "confidentialapplication", "app"}:
                return extender._update_identity_resource(resource, norm, new_value)
            if norm in {"dynamicgroup", "dynamicresourcegroup"}:
                return extender._update_dynamic_group_classic(resource, region, new_value)
            if norm == "policy":
                return extender._update_policy_classic(resource, region, new_value)

        if self.extend_strategy == ActionStrategy.EXTEND_BULK_TAG:
            bulk_result, bulk_success = extender._try_bulk_extend(resource, region, new_value)
            if bulk_success and bulk_result:
                extender.logger.info("Bulk extend succeeded for %s (%s)", rtype, ocid)
                bulk_result.metadata.setdefault("method", "bulk")
                return bulk_result
            extender.logger.error(
                "Bulk supported resource failed via bulk extend: %s (%s)",
                rtype, ocid,
            )
            return bulk_result or Result(
                HTTPStatus.NOT_IMPLEMENTED,
                message=f"Bulk extend failed for {rtype} {ocid}",
                metadata={"identifier": ocid, "resource_type": rtype},
            )

        if self.extend_strategy == ActionStrategy.EXTEND_SDK_TAG:
            handler_name = self.extend_handler
            updater = getattr(extender, handler_name, None) if handler_name else None
            if not updater:
                updater = extender.update_tag_tree.get(norm)
            if not updater:
                extender.logger.error("No extend implementation for %s (%s)", rtype, ocid)
                return Result(
                    HTTPStatus.NOT_IMPLEMENTED,
                    message=f"No extender implementation for {rtype}",
                    metadata={"identifier": ocid, "resource_type": rtype},
                )
            try:
                response = updater(resource, region, new_value, defined_tags)
                status = getattr(response, "status", response)
                return Result(
                    status=status,
                    message=f"Expiry extended to {new_value}",
                    metadata={
                        "identifier": ocid,
                        "resource_type": rtype,
                        "region": region,
                        "method": "sdk",
                    },
                )
            except Exception:
                extender.logger.exception("SDK extend failed for %s (%s)", rtype, ocid)
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

        return Result(
            HTTPStatus.NOT_IMPLEMENTED,
            message=f"No extender implementation for {rtype}",
            metadata={"identifier": ocid, "resource_type": rtype},
        )
