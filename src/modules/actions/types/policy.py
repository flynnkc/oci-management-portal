#!/usr/bin/python3.11
from http import HTTPStatus

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
