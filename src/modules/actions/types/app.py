#!/usr/bin/python3.11
from http import HTTPStatus

from oci.identity_domains.models import Operations, PatchOp

from .base import ActionStrategy
from ..result import Result
from ._identity_domain import IdentityDomainResource


class AppResource(IdentityDomainResource):
    resource_type = 'App'
    delete_strategy = ActionStrategy.DELETE_FORCE
    extend_strategy = ActionStrategy.EXTEND_IDENTITY

    def force_delete(self, deleter, resource):
        client = self._get_identity_domain_client(deleter, resource)
        app_id = resource["identifier"]

        patch = PatchOp(
            schemas=["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            operations=[
                Operations(op="REPLACE", path="active", value=False),
            ],
        )

        try:
            client.patch_app(app_id=app_id, patch_op=patch)
            deleter.logger.info("Deactivated app %s before delete", app_id)
        except Exception as exc:
            deleter.logger.warning(
                "Deactivate failed (may already be inactive) %s: %s",
                app_id,
                exc,
            )

        client.delete_app(app_id=app_id, force_delete=True)
        deleter.logger.info("Deleted app %s", app_id)
        return Result(
            status=HTTPStatus.OK,
            metadata={"method": "force", "resource_type": "App", "identifier": app_id},
        )
