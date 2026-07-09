#!/usr/bin/python3.11

import copy
from http import HTTPStatus

from oci.exceptions import ServiceError
from oci.identity_domains.models import Operations, PatchOp

from .base import BaseResourceType
from ..result import Result


class IdentityDomainResource(BaseResourceType):
    # Shared helper for resources that may live in any active identity domain.
    # This module is private, so BaseAction discovery skips it and only concrete
    # resource modules register support.
    def _get_identity_domain_client(self, action, resource):
        resource_ocid = resource["identifier"]
        rtype = resource.get("resource_type")

        if resource_ocid in action._domain_client_cache:
            return action._domain_client_cache[resource_ocid]

        for client in action._iter_identity_domain_clients(resource):
            try:
                if rtype == "User":
                    client.get_user(user_id=resource_ocid)
                elif rtype == "Group":
                    client.get_group(group_id=resource_ocid)
                elif rtype == "DynamicResourceGroup":
                    client.get_dynamic_resource_group(
                        dynamic_resource_group_id=resource_ocid
                    )
                elif rtype == "App":
                    client.get_app(app_id=resource_ocid)
                else:
                    continue

                action._domain_client_cache[resource_ocid] = client
                return client

            except ServiceError as exc:
                if exc.status == 404:
                    continue
                raise

        raise Exception(f"Resource {resource_ocid} not found in any Identity Domain")

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

    def extend(self, extender, resource, region, new_value, defined_tags) -> Result:
        resource = {**resource, "resource_type": self.resource_type}
        client = self._get_identity_domain_client(extender, resource)
        resource_ocid = resource["identifier"]
        tags = copy.deepcopy(resource.get("defined_tags", {}))
        tags.setdefault(extender.tag_namespace, {})
        tags[extender.tag_namespace][extender.tag_key] = new_value
        tag_list = self._convert_defined_tags_to_list(tags)
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

        if self.resource_type == "User":
            response = client.patch_user(user_id=resource_ocid, patch_op=patch)
        elif self.resource_type == "Group":
            response = client.patch_group(group_id=resource_ocid, patch_op=patch)
        elif self.resource_type == "App":
            response = client.patch_app(app_id=resource_ocid, patch_op=patch)
        else:
            return super().extend(extender, resource, region, new_value, defined_tags)

        status = getattr(response, "status", HTTPStatus.OK)
        return Result(
            status=status,
            message=f"Expiry extended to {new_value}",
            metadata={
                "identifier": resource_ocid,
                "resource_type": self.resource_type,
                "method": "identity",
            },
        )
