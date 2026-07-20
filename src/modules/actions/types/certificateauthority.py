#!/usr/bin/python3.11
from oci.certificates_management.models import UpdateCertificateAuthorityDetails

from .base import ActionStrategy, BaseResourceType


class CertificateAuthorityResource(BaseResourceType):
    resource_type = 'CertificateAuthority'
    aliases = ('certificateauthority', 'certificate_authority')
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = 'certificates_management_client'
    delete_method_name = 'change_certificate_authority_compartment'
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'certificates_management_client'
    extend_method_name = 'update_certificate_authority'
    extend_identifier_param = 'certificate_authority_id'
    extend_details_param = 'update_certificate_authority_details'
    extend_details_cls = UpdateCertificateAuthorityDetails
