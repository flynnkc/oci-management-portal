#!/usr/bin/python3.11
from .base import ActionStrategy, BaseResourceType


class WaasCertificateResource(BaseResourceType):
    resource_type = 'WaasCertificate'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
