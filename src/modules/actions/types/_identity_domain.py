#!/usr/bin/python3.11

from oci.exceptions import ServiceError

from .base import BaseResourceType


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
