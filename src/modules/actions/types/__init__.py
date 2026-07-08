#!/usr/bin/python3.11

"""
BaseResourceType plugins live in this package. Each non-private module should define
one BaseResourceType subclass for one OCI resource type. BaseAction imports every
non-private module here, so adding actions/types/myresource.py is enough to
register support for Deleter/Extender.

Simple declarative resource:

    from .base import ActionStrategy, BaseResourceType


    class InstanceResource(BaseResourceType):
        resource_type = "Instance"
        delete_strategy = ActionStrategy.DELETE_BULK_MOVE
        extend_strategy = ActionStrategy.EXTEND_BULK_TAG

SDK move plus SDK tag resource:

    from .base import ActionStrategy, BaseResourceType


    class LogGroupResource(BaseResourceType):
        resource_type = "LogGroup"
        delete_strategy = ActionStrategy.DELETE_SDK_MOVE
        delete_client_attr = "logging_management_client"
        delete_method_name = "change_log_group_compartment"
        extend_strategy = ActionStrategy.EXTEND_SDK_TAG
        extend_handler = "update_log_group"

Custom behavior can override delete(), force_delete(), or extend() when one of
the shared strategies is not enough.
"""

from .base import (
    ActionKind,
    ActionStrategy,
    BaseResourceType,
    ResourceActionRegistry,
    ResourceActionSpec,
    normalize_resource_type,
)

__all__ = (
    "ActionKind",
    "ActionStrategy",
    "BaseResourceType",
    "ResourceActionRegistry",
    "ResourceActionSpec",
    "normalize_resource_type",
)
