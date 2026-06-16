#!/usr/bin/python3.11

import logging
from collections.abc import Callable

from oci import resource_search
from oci.identity import IdentityClient
from oci.identity.models import RegionSubscription
from oci.signer import Signer
from oci.response import Response
from oci.util import to_dict
from oci.pagination import list_call_get_all_results

from .filter import AbstractFilter
from .query import Query
from .compartment_mapper import CompartmentMapper
from ..utils import log_factory


class Search:

    resource_default = 'all'

    def __init__(
        self,
        tag: str,
        key: str,
        config: dict,
        signer: Signer,
        query: Query,
        handler: logging.Handler = logging.StreamHandler(),
        log_level: int | str = logging.INFO,
        signer_factory: Callable[[], Signer] | None = None,
    ) -> None:
        self.logger = log_factory(__name__, log_level, handler)

        self.client: dict[str, resource_search.ResourceSearchClient] = {}
        self.signer_factory = signer_factory
        self.tag: str = tag
        self.key: str = key
        self.filter: AbstractFilter = AbstractFilter()
        self.base_query = query

        self.home_region: str = ''
        self.region_names: list[str] = []
        self.region_keys: list[str] = []

        self.set_regions(config, signer=signer)
        self.set_clients(config, signer=signer)
        self.resource_list: list[str] = self.get_resource_types()

        self.compartment_map = CompartmentMapper(
            config,
            signer,
            log_factory(
                'CompartmentMapper',
                log_level, handler))

        self.logger.debug(f'Created Search: {self}')

    def __repr__(self) -> str:
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
        page: str | None = None,
        limit: int = 1000,
        resource=resource_default,
        explicit_query: str | None = None,
        **kwargs
    ) -> Response:

        query = explicit_query or self.base_query.string(resource, user)

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

        results = self.filter.results(results)

        # Add compartment paths to additional_details
        for item in results.data.items:
            if not hasattr(item, "additional_details") or item.additional_details is None:
                item.additional_details = {}

            compartment_id = getattr(item, "compartment_id", None)
            if compartment_id:
                path = self.compartment_map.get_compartment_path(compartment_id)
                item.additional_details.update({'compartmentPath': path})

        return results

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

        item = items[0]

        # Add compartment path safely for dict data
        compartment_id = item.get("compartment_id") or item.get("compartmentId")
        additional_details = item.get("additional_details") or {}

        if compartment_id:
            path = self.compartment_map.get_compartment_path(compartment_id)
            additional_details.update({'compartmentPath': path})

        item["additional_details"] = additional_details

        return item

    def validate_resource(self, username: str, ocid: str, **kwargs) -> bool:
        self.logger.debug(f'Checking if {username} owns {ocid}')

        item = self.get_resource_by_id(ocid, **kwargs)
        if not item:
            self.logger.warning(f'no resource returned for {ocid}')
            return False

        try:
            owner = item['defined_tags'][self.tag][self.key]
            self.logger.debug(
                f'owner of {ocid} listed as {self.tag}/{self.key}={owner}')
        except KeyError:
            self.logger.exception(f'exception trying to get tags on resource {ocid}')
            return False

        owns = username.lower() == owner.lower()
        self.logger.debug(f'{username} ownership of {ocid}: {owns}')
        return owns

    def get_resource_types(self) -> list[str]:
        response = list_call_get_all_results(
            self.client[self.home_region].list_resource_types,
            limit=1000
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
            regional_signer = self.signer_factory() if self.signer_factory else signer
            if regional_signer:
                regional_signer.region = region
                self.client[region] = resource_search.ResourceSearchClient(
                    config, signer=regional_signer
                )
            else:
                self.client[region] = resource_search.ResourceSearchClient(config)


class SearchError(Exception):
    def __init__(self, error) -> None:
        self.error = error

    def __str__(self) -> str:
        return repr(self.error)
