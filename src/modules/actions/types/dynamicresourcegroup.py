#!/usr/bin/python3.11
from http import HTTPStatus

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
