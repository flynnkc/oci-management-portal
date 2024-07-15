#!/usr/bin/python3.11

import datetime
import logging

from oci import resource_search

from oci.signer import Signer
from oci.response import Response
from oci.util import to_dict

from .filter import AbstractFilter, ExpiryFilter

class Search:
    resource_list = [
        'analyticsinstance',
        'apigateway',
        'application',
        'autonomousdatabase',
        'autonomouscontainerdatabase',
        'bastion',
        'bigdataservice',
        'bootvolume',
        'bucket',
        'cabundle',
        'certificate',
        'certificateauthority',
        'cloudexadatainfrastructure',
        'cloudvmcluster',
        'clusterscluster',
        'clustersvirtualnode',
        'containerinstance',
        'containerrepo',
        'compartment',
        'datacatalog',
        'datalabelingdataset',
        'datasciencemodel',
        'datasciencenotebooksession',
        'datascienceproject',
        'dbsystem',
        'dedicatedvmhost',
        'devopsproject',
        'disworkspace',
        'drg',
        'drprotectiongroup',
        'emailsender',
        'emaildomain',
        'eventrule',
        'filesystem',
        'functionsapplication',
        'group',
        'key',
        'mounttarget',
        'networkfirewall',
        'networkfirewallpolicy',
        'goldengatedeployment',
        'identityprovider',
        'image',
        'instance',
        'instancepool',
        'integrationinstance',
        'ipsecconnection',
        'loadbalancer',
        'localpeeringgateway',
        'log',
        'odainstance',
        'onstopic',
        'ormstack',
        'policy',
        'publicip',
        'serviceconnector',
        'stream',
        'tagnamespace',
        'user',
        'vault',
        'vaultsecret',
        'vbsinstance',
        'vcn',
        'visualbuilderinstance',
        'vmcluster',
        'vmwaresddc',
        'volume',
        'waaspolicy'
        ]
    
    resources = ', '.join(resource_list)
    
    def __init__(self, tag: str, key: str, config: dict, signer: Signer=None,
                 log_level: int=30):
        self.client = resource_search.ResourceSearchClient(config, signer=signer)
        self.tag = tag
        self.key = key
        self.filter = AbstractFilter()

        # Logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        handler = logging.StreamHandler()
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
        self.logger.addHandler(handler)
        self.logger.debug(f'Created Search with tag {self.tag}.{self.key}')

    def set_filter(self, filter: AbstractFilter):
        self.filter = filter

    # Get resources created by user
    # Query tag format namespace.key = domain/username
    # Kwarg resources
    def get_user_resources(self, user: str, page: str=None, limit: int=25, **kwargs) -> Response:
        # Can't 'return allAdditionalFields' with 'all' resource type
        query =  (f"query {kwargs.get('resource', Search.resources)} resources where "
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
        if result.status is not 200:
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
        if result.status is not 200:
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
    

class SearchError(Exception):
    def __init__(self, error):
        self.error = error

    def __str__(self):
        return(repr(self.error))