#!/usr/bin/python3.11
from http import HTTPStatus

from .base import ActionStrategy
from ..result import Result
from ._identity_domain import IdentityDomainResource


class GroupResource(IdentityDomainResource):
    resource_type = 'Group'
    delete_strategy = ActionStrategy.DELETE_FORCE
    extend_strategy = ActionStrategy.EXTEND_IDENTITY

    def force_delete(self, deleter, resource):
        client = self._get_identity_domain_client(deleter, resource)
        group_id = resource["identifier"]
        client.delete_group(group_id=group_id, force_delete=True)
        return Result(
            status=HTTPStatus.OK,
            metadata={"method": "force", "resource_type": "Group", "identifier": group_id},
        )
