#!/usr/bin/python3.11
from oci.data_science.models import UpdateNotebookSessionDetails

from .base import ActionStrategy, BaseResourceType


class DataScienceNotebookSessionResource(BaseResourceType):
    resource_type = 'DataScienceNotebookSession'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = 'data_science_client'
    extend_method_name = 'update_notebook_session'
    extend_identifier_param = 'notebook_session_id'
    extend_details_param = 'update_notebook_session_details'
    extend_details_cls = UpdateNotebookSessionDetails
