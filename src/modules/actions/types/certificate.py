#!/usr/bin/python3.11
from oci.certificates_management.models import UpdateCertificateDetails

from .base import ActionStrategy, BaseResourceType


class CertificateResource(BaseResourceType):
    resource_type = 'Certificate'
    aliases = ('certificate', 'certificates')
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'certificates_management_client'
    delete_method_name = 'change_certificate_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'certificates_management_client'
    extend_method_name = 'update_certificate'
    extend_identifier_param = 'certificate_id'
    extend_details_param = 'update_certificate_details'
    extend_details_cls = UpdateCertificateDetails
