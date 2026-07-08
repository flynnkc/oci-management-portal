#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class EmaildomainResource(BaseResourceType):
    resource_type = 'emaildomain'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
