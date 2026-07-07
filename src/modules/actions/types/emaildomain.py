#!/usr/bin/python3.11
from ..resource import ActionStrategy, ResourceType


class EmaildomainResource(ResourceType):
    resource_type = 'emaildomain'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
