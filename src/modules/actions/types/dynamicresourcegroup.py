#!/usr/bin/python3.11
import copy
from http import HTTPStatus

import oci

from .base import ActionStrategy
from ..result import Result
from ._identity_domain import IdentityDomainResource


class DynamicResourceGroupResource(IdentityDomainResource):
    resource_type = 'DynamicResourceGroup'
    delete_strategy = ActionStrategy.DELETE_FORCE
    extend_strategy = ActionStrategy.EXTEND_IDENTITY

    def force_delete(self, deleter, resource):
        client = self._get_identity_domain_client(deleter, resource)
        drg_id = resource["identifier"]
        client.delete_dynamic_resource_group(
            dynamic_resource_group_id=drg_id,
            force_delete=True,
        )
        return Result(
            status=HTTPStatus.OK,
            metadata={
                "method": "force",
                "resource_type": "DynamicResourceGroup",
                "identifier": drg_id,
            },
        )

    def extend(self, extender, resource, region, new_value, defined_tags) -> Result:
        tags = copy.deepcopy(resource.get("defined_tags", {}))
        tags.setdefault(extender.tag_namespace, {})
        tags[extender.tag_namespace][extender.tag_key] = new_value
        freeform_tags = resource.get("freeformTags", {}) or {}
        response = extender.clients[region].identity_client.update_dynamic_group(
            dynamic_group_id=resource["identifier"],
            update_dynamic_group_details=oci.identity.models.UpdateDynamicGroupDetails(
                defined_tags=tags,
                freeform_tags=freeform_tags,
            ),
        )
        status = getattr(response, "status", HTTPStatus.OK)
        return Result(
            status=status,
            message=f"Expiry extended to {new_value}",
            metadata={
                "identifier": resource["identifier"],
                "resource_type": "DynamicResourceGroup",
                "region": region,
                "method": "identity",
            },
        )
