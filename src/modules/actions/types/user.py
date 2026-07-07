#!/usr/bin/python3.11

from ..resource import ActionStrategy, ResourceType


class UserResource(ResourceType):
    # Identity resources use specialized Deleter/Extender helpers because they
    # may live in identity domains rather than ordinary regional service APIs.
    resource_type = 'User'
    delete_strategy = ActionStrategy.DELETE_FORCE
    extend_strategy = ActionStrategy.EXTEND_IDENTITY
