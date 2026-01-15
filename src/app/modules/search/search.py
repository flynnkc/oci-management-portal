#!/usr/bin/python3.11

import logging
import logging.handlers

from oci import resource_search
from oci.identity import IdentityClient
from oci.identity.models import RegionSubscription
from oci.signer import Signer
from oci.response import Response
from oci.util import to_dict
from oci.pagination import list_call_get_all_results

from .filter import AbstractFilter
from ..utils import log_factory


class Search:

    resource_default = 'all'

    def __init__(
        self,
        tag: str,
        key: str,
        config: dict,
        signer: Signer = None,
        handler: logging.Handler = logging.StreamHandler(),
        log_level: int | str = 30
    ):
        self.logger = log_factory(__name__, log_level, handler)

        self.client: dict[str, resource_search.ResourceSearchClient] = {}
        self.tag: str = tag
        self.key: str = key
        self.filter: AbstractFilter = AbstractFilter()

        self.home_region: str = ''
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

    def get_user_resources(
        self,
        user: str,
        page: str = None,
        limit: int = 100,
        resource=resource_default,
        **kwargs
    ) -> Response:

        query = (
            f"query {resource} resources where definedTags.namespace = "
            f"'{self.tag}' && definedTags.key = '{self.key}' && "
            f"definedTags.value = '{user}' && lifeCycleState != 'TERMINATED' && "
            f"lifeCycleState != 'TERMINATING'"
        )

        self.logger.debug(f'get_user_resources query: {query}')

        details = resource_search.models.StructuredSearchDetails(query=query)

        results = self.client[
            kwargs.get('region', self.home_region)
        ].search_resources(details, page=page, limit=limit)

        self.logger.info(
            "Search debug → returned_items=%d next_page=%s limit=%s page=%s region=%s",
            len(results.data.items or []),
            results.next_page,
            limit,
            page,
            kwargs.get('region', self.home_region)
        )

        if results.status != 200:
            self.logger.error(f'Non-200 Search result: {results}')
            raise SearchError(f'Search response {results.status}')

        return self.filter.results(results)


    def get_resource_by_id(self, ocid: str, **kwargs) -> dict | None:
        self.logger.debug(f'Searching for resource {ocid}')

        query = f"query all resources where identifier = '{ocid}'"
        details = resource_search.models.StructuredSearchDetails(query=query)

        result = self.client[
            kwargs.get('region', self.home_region)
        ].search_resources(details)

        if result.status != 200:
            self.logger.error(f'Search status code {result.status}')
            return None

        data = to_dict(result.data)
        items = data.get("items", [])

        if not items:
            self.logger.warning(f'No resource found for OCID {ocid}')
            return None

        if len(items) > 1:
            self.logger.warning(
                f'Get_resource_by_id returned more than one result for {ocid}'
            )

        return items[0]

    def validate_resource(self, username: str, ocid: str, **kwargs) -> bool:
        self.logger.debug(f'Checking if {username} owns {ocid}')

        query = f"query all resources where identifier = '{ocid}'"
        details = resource_search.models.StructuredSearchDetails(query=query)

        result = self.client[
            kwargs.get('region', self.home_region)
        ].search_resources(details)

        if result.status != 200:
            self.logger.error(f'Search status code {result.status}')
            return False

        items = to_dict(result.data).get("items", [])

        if not items:
            return False

        try:
            owner = items[0]['defined_tags'][self.tag][self.key]
        except KeyError:
            return False

        return username == owner

    def get_resource_types(self) -> list[str]:
        response = list_call_get_all_results(
            self.client[self.home_region].list_resource_types
        )

        if response.status != 200:
            self.logger.critical(
                f'Unable to pull resource list for search: {response.status}'
            )
            raise SystemExit

        resource_list = [data.name for data in response.data]
        self.logger.info(f'Number resources returned: {len(resource_list)}')

        return resource_list

    def set_regions(self, config: dict, **kwargs):
        client = IdentityClient(config, **kwargs)
        response = client.list_region_subscriptions(config['tenancy'])

        if response.status != 200:
            self.logger.critical(
                f'Unable to get subscribed regions: {response.status}'
            )
            raise SystemExit

        for region in response.data:
            if region.status == RegionSubscription.STATUS_READY:
                self.region_keys.append(region.region_key)
                self.region_names.append(region.region_name)
                if region.is_home_region:
                    self.home_region = region.region_name

        self.region_keys.sort()
        self.region_names.sort()

    def set_clients(self, config: dict, signer=None):
        for region in self.region_names:
            config['region'] = region
            if signer:
                signer.region = region
                self.client[region] = resource_search.ResourceSearchClient(
                    config, signer=signer
                )
            else:
                self.client[region] = resource_search.ResourceSearchClient(config)


class SearchError(Exception):
    def __init__(self, error):
        self.error = error

    def __str__(self):
        return repr(self.error)

