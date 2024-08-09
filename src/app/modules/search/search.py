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

    # Resource type to default to in search
    resource_default = 'all'

    def __init__(self, tag: str, key: str, config: dict, signer: Signer=None,
                 log_level: int=30):
        # Logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        handler = logging.StreamHandler()
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
        self.logger.addHandler(handler)

        # Instance Variables
        #self.client: resource_search.ResourceSearchClient = (
        #    resource_search.ResourceSearchClient(config, signer=signer))
        self.client: dict[str, resource_search.ResourceSearchClient] = {}
        self.tag: str = tag
        self.key:str = key
        self.filter: str = AbstractFilter()

        # Regions set first
        self.home_region: str = '' # ex. us-ashburn-1
        self.region_names: list[str] = []
        self.region_keys: list[str] = []
        self.set_regions(config, signer=signer)

        self.set_clients(config, signer=signer)
        self.resource_list: list[str] = self.get_resource_types()

        self.logger.debug(f'Created Search: {self}')

    def __repr__(self):
        sep = '\n\t'
        return f'''Search
    Tag: {self.tag}
    Key: {self.key}
    Filter: {self.filter}
    Home Region: {self.home_region}
    Regions: 
        {sep.join(self.region_names)}
    Region Keys:
        {sep.join(self.region_keys)}
    Resource Listings:
        {sep.join(self.resource_list)}
        '''

    def set_filter(self, filter: AbstractFilter):
        self.filter = filter

    def get_user_resources(self, user: str, page: str=None, limit: int=25,
                           resource=resource_default, **kwargs) -> Response:
        '''Get resources created by user. Support pagination via page, limits on
        number of resources to return, and filtering on resource type.

        Keyword arguments:
        region -- region name for client selection (default home region)
        '''

        # Can't 'return allAdditionalFields' with 'all' resource type
        query =  (f"query {resource} resources where definedTags.namespace = "
                  f"'{self.tag}' && definedTags.key = '{self.key}' && "
                  f"definedTags.value = '{user}' && lifeCycleState != 'TERMINATED' &&"
                   " lifeCycleState != 'TERMINATING'")
        self.logger.debug(f'get_user_resources query: {query}')

        details = resource_search.models.StructuredSearchDetails(query=query)

        results = self.client[kwargs.get('region', self.home_region)].search_resources(
            details, page=page, limit=limit)
        if results.status != 200:
            self.logger.error(f'Non-200 Search result: {results}')
            raise SearchError(f'Search response {results.status}')
        
        # Call filter before returning results
        return self.filter.results(results)
    
    def get_resource_by_id(self, ocid: str, **kwargs) -> dict:
        '''Return a single resource that is looked up by unique OCID.

        Keyword arguments:
        region -- region name for client selection (default home region)
        '''

        self.logger.debug(f'Searching for resource {ocid}')

        query = f"query all resources where identifier = '{ocid}'"
        details = resource_search.models.StructuredSearchDetails(query=query)
        result = self.client[kwargs.get('region', self.home_region)].search_resources(
            details)
        if result.status != 200:
            self.logger.error(f'Search status code {result.status}')

        result = to_dict(result.data)

        # Validate number of results
        if len(result) > 1:
            self.logger.error(f'Get_resource_by_id returned more than 1 result: {result}')

        return result[0]
    
    def validate_resource(self, username: str, ocid: str, **kwargs) -> bool:
        '''Validate that a resource belongs to user. Looks up user by username and
        resource by OCID.

        Keyword arguments:
        region -- region name for client selection (default home region)
        '''
                
        self.logger.debug(f'Checking if {username} owns {ocid}')

        query = f"query all resources where identifier = '{ocid}'"
        details = resource_search.models.StructuredSearchDetails(query=query)
        result = self.client[kwargs.get('region', self.home_region)].search_resources(
            details)
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
        response = list_call_get_all_results(
            self.client[self.home_region].list_resource_types)

        if response.status != 200:
            self.logger.critical(
                f'Unable to pull resource list for search: {response.status}')
            raise SystemExit
        
        resource_list = [data.name for data in response.data]
        self.logger.info(
            f'Number resources returned: {len(resource_list)}\n'
        )
        
        return resource_list
        
    # Assign subscribed regions to search instance; Needs config and signer kwarg
    # because need to create single use identity client to get region subscriptions
    def set_regions(self, config: dict, **kwargs):
        # Different client only used once for this operation
        client = IdentityClient(config, **kwargs)
        response = client.list_region_subscriptions(config['tenancy'])

        if response.status != 200:
            self.logger.critical(
                f'Unable to get subscribed regions: {response.status}')
            raise SystemExit
        
        # Filter out any regions that are not ready
        for region in response.data:
            if region.status == RegionSubscription.STATUS_READY:
                self.region_keys.append(region.region_key)
                self.region_names.append(region.region_name)
                if region.is_home_region:
                    self.home_region = region.region_name

        # Put in alphabetical order
        self.region_keys = sorted(self.region_keys)
        self.region_names = sorted(self.region_names)

    # Creates clients for each subscribed region, depends on regions
    def set_clients(self, config: dict, signer=None, **kwargs):
        for region in self.region_names:
            config['region'] = region
            if signer:
                signer.region = region
                self.client[region] = resource_search.ResourceSearchClient(
                    config, signer=signer)
            else:
                self.client[region] = resource_search.ResourceSearchClient(config)
    

class SearchError(Exception):
    def __init__(self, error):
        self.error = error

    def __str__(self):
        return(repr(self.error))