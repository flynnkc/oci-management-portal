#!/usr/bin/python3.11

import logging

from oci import resource_search

from oci.identity import IdentityClient
from oci.identity.models import RegionSubscription
from oci.signer import Signer
from oci.response import Response
from oci.util import to_dict
from oci.pagination import list_call_get_all_results

from .filter import AbstractFilter

class Search:
    def __init__(self, tag: str, key: str, config: dict, signer: Signer=None,
                 log_level: int=30):
        self.client: resource_search.ResourceSearchClient = (
            resource_search.ResourceSearchClient(config, signer=signer))
        self.tag: str = tag
        self.key:str = key
        self.filter: str = AbstractFilter()

        # Logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        handler = logging.StreamHandler()
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
        self.logger.addHandler(handler)
        self.logger.debug(f'Created Search with tag {self.tag}.{self.key}')

        self.resource_list: list[str] = self.get_resource_types()
        self.regions: list[RegionSubscription] = self.get_regions(config,
                                                                  signer=signer)

    def set_filter(self, filter: AbstractFilter):
        self.filter = filter

    # Get resources created by user
    # Query tag format namespace.key = domain/username
    # Kwarg resources
    def get_user_resources(self, user: str, page: str=None, limit: int=25, **kwargs) -> Response:
        # Can't 'return allAdditionalFields' with 'all' resource type
        query =  (f"query {kwargs.get('resource', 'all')} resources where "
                  f"definedTags.namespace = '{self.tag}' && definedTags.key = "
                  f"'{self.key}' && definedTags.value = '{user}' && lifeCycleState "
                   "!= 'TERMINATED' && lifeCycleState != 'TERMINATING'")
        self.logger.debug(f'get_user_resources query: {query}')

        details = resource_search.models.StructuredSearchDetails(query=query)

        results = self.client.search_resources(details, page=page, limit=limit)
        if results.status != 200:
            self.logger.error(f'Non-200 Search result: {results}')
            raise SearchError(f'Search response {results.status}')
        
        # Call filter before returning results
        return self.filter.results(results)
    
    # Return a single resource that is looked up by unique OCID
    def get_resource_by_id(self, ocid: str) -> dict:
        self.logger.debug(f'Searching for resource {ocid}')

        query = f"query all resources where identifier = '{ocid}'"
        details = resource_search.models.StructuredSearchDetails(query=query)
        result = self.client.search_resources(details)
        if result.status != 200:
            self.logger.error(f'Search status code {result.status}')

        result = to_dict(result.data)

        # Validate number of results
        if len(result) > 1:
            self.logger.error(f'Get_resource_by_id returned more than 1 result: {result}')

        return result[0]
    
    def validate_resource(self, username: str, ocid: str) -> bool:
        self.logger.debug(f'Checking if {username} owns {ocid}')

        query = f"query all resources where identifier = '{ocid}'"
        details = resource_search.models.StructuredSearchDetails(query=query)
        result = self.client.search_resources(details)
        if result.status != 200:
            self.logger.error(f'Search status code {result.status}')

        result = to_dict(result.data)['items']
        # Result should only have 1 or 0 items
        if len(result) > 1:
            self.logger.error(f'Get_resource_by_id returned more than 1 result: {result}')
        try:
            owner = result[0]['defined_tags'][self.tag][self.key]
        except KeyError as e:
            self.logger.error(f'{e}\n{result}')
            return False

        self.logger.debug(f'Owner of {ocid} is {owner}')

        return username == owner
    
    # Return a list of searchable resource types as a list
    def get_resource_types(self, **kwargs) -> list[str]:
        response = list_call_get_all_results(self.client.list_resource_types)

        if response.status != 200:
            self.logger.critical(
                f'Unable to pull resource list for search: {response.status}')
            raise SystemExit
        
        resource_list = [data.name for data in response.data]
        self.logger.info(
            f'Number resources returned: {len(resource_list)}\n'
        )
        self.logger.debug(
            f'Response - Status: {response.status}\n'
            f'\tSupported resources for search: {", ".join(resource_list)}'
            )
        
        return resource_list
        
    # Return a list of subscibed regions objects; Needs config and signer kwarg
    # because need to create single use identity client to get region subscriptions
    def get_regions(self, config: dict, **kwargs) -> list[RegionSubscription]:
        # Different client only used once for this operation
        client = IdentityClient(config, **kwargs)
        response = client.list_region_subscriptions(config['tenancy'])

        if response.status != 200:
            self.logger.critical(
                f'Unable to get subscribed regions: {response.status}')
            raise SystemExit
        
        regions = []
        # Filter out any regions that are not ready
        for region in response.data:
            if region.status == RegionSubscription.STATUS_READY:
                regions.append(region)

        self.logger.debug(f'Returned regions: {regions}')

        return regions
    

class SearchError(Exception):
    def __init__(self, error):
        self.error = error

    def __str__(self):
        return(repr(self.error))