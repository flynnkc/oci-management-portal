#!/usr/bin/python3.11
import copy
from http import HTTPStatus

import oci

from .base import ActionStrategy, BaseResourceType
from ..result import Result


class PolicyResource(BaseResourceType):
    resource_type = 'Policy'
    delete_strategy = ActionStrategy.DELETE_FORCE
    extend_strategy = ActionStrategy.EXTEND_IDENTITY

    def force_delete(self, deleter, resource):
        policy_id = resource["identifier"]
        home_region = deleter._get_tenancy_home_region_name()

        if home_region not in deleter.clients:
            deleter.clients[home_region] = deleter._build_client_for_region(home_region)

        deleter.clients[home_region].identity_client.delete_policy(policy_id=policy_id)
        return Result(
            status=HTTPStatus.OK,
            metadata={"method": "force", "resource_type": "Policy", "identifier": policy_id},
        )

    def extend(self, extender, resource, region, new_value, defined_tags) -> Result:
        tags = copy.deepcopy(resource.get("defined_tags", {}))
        tags.setdefault(extender.tag_namespace, {})
        tags[extender.tag_namespace][extender.tag_key] = new_value
        update_details = oci.identity.models.UpdatePolicyDetails(
            defined_tags=tags,
            freeform_tags=resource.get("freeformTags", {}) or {},
        )
        response = extender.clients[region].identity_client.update_policy(
            policy_id=resource["identifier"],
            update_policy_details=update_details,
        )
        status = getattr(response, "status", HTTPStatus.OK)
        return Result(
            status=status,
            message=f"Expiry extended to {new_value}",
            metadata={
                "identifier": resource["identifier"],
                "resource_type": "Policy",
                "region": region,
                "method": "identity",
            },
        )
