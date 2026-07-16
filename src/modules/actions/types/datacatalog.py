#!/usr/bin/python3.11
from oci.data_catalog.models import UpdateCatalogDetails
from .base import ActionStrategy, BaseResourceType


class DataCatalogResource(BaseResourceType):
    resource_type = 'DataCatalog'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'data_catalog_client'
    extend_method_name = 'update_catalog'
    extend_identifier_param = 'catalog_id'
    extend_details_param = 'update_catalog_details'
    extend_details_cls = UpdateCatalogDetails
