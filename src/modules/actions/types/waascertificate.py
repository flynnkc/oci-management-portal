#!/usr/bin/python3.11
from oci.waas.models import UpdateCertificateDetails

from .base import ActionStrategy, BaseResourceType


class WaasCertificateResource(BaseResourceType):
    resource_type = 'WaasCertificate'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'waas_client'
    extend_method_name = 'update_certificate'
    extend_identifier_param = 'certificate_id'
    extend_details_param = 'update_certificate_details'
    extend_details_cls = UpdateCertificateDetails
