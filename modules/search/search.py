#!/usr/bin/python3.11

import datetime
import logging

from oci import resource_search

from oci.signer import Signer
from oci.response import Response

class Search:
    def __init__(self, tag, key: str, config: dict, signer: Signer=None):
        self.client = resource_search.ResourceSearchClient(config, signer=signer)
        self.tag = tag
        self.key = key
        self.log = logging.getLogger(__name__)

    # Get resources created by user
    # Query tag format namespace.key = domain/username
    def get_user_resources(self, user: str, page: str=None) -> Response:
        query =  f"query all resources where definedTags.namespace = '{self.tag}' && "
        query += f"definedTags.key = '{self.key}' && definedTags.value = '{user}'"
        self.log.debug(f'get_user_resources query: {query}')

        details = resource_search.models.StructuredSearchDetails(query=query)

        # Filter response.data before returning
        return self.filter_expired(self.client.search_resources(details, page=page, limit=10))
        

    # This method filters out non-exipred resources
    def filter_expired(self, query_results: Response) -> Response:
        now = datetime.datetime.now()

        return query_results