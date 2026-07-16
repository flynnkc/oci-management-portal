#!/usr/bin/python3.11
from oci.data_science.models import UpdateModelDetails
from .base import ActionStrategy, BaseResourceType


class DataScienceModelResource(BaseResourceType):
    resource_type = 'DataScienceModel'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'data_science_client'
    extend_method_name = 'update_model'
    extend_identifier_param = 'model_id'
    extend_details_param = 'update_model_details'
    extend_details_cls = UpdateModelDetails

