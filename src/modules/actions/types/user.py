#!/usr/bin/python3.11

from http import HTTPStatus

from .base import ActionStrategy
from ..result import Result
from ._identity_domain import IdentityDomainResource


class UserResource(IdentityDomainResource):
    # Identity resources use specialized Deleter/Extender helpers because they
    # may live in identity domains rather than ordinary regional service APIs.
    resource_type = 'User'
    delete_strategy = ActionStrategy.DELETE_FORCE
    extend_strategy = ActionStrategy.EXTEND_IDENTITY

    def force_delete(self, deleter, resource):
        client = self._get_identity_domain_client(deleter, resource)
        user_id = resource["identifier"]

        try:
            grants = client.list_grants(filter=f'user eq "{user_id}"').data
            for grant in grants:
                try:
                    client.delete_grant(grant_id=grant.id)
                    deleter.logger.info("Removed grant %s for user %s", grant.id, user_id)
                except Exception as exc:
                    deleter.logger.warning("Grant removal failed %s: %s", grant.id, exc)
        except Exception as exc:
            deleter.logger.warning("Grant listing failed for %s: %s", user_id, exc)

        client.delete_user(user_id=user_id, force_delete=True)
        return Result(
            status=HTTPStatus.OK,
            metadata={"method": "force", "resource_type": "User", "identifier": user_id},
        )
