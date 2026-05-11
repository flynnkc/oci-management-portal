#!/usr/pyton3.11

import logging

from string import Template

from ..utils import log_factory


class Query:
    """Query is meant to be a superclass to create queries. Instead of
        defining query logic in the Search class, a Query can be used to craft
        query strings to be consumed by search to fit the needs of the Search.

        Methods:
        
        query will be used to create and return the query string to the
            Search object. This method should be overwritten by subclasses to define
            the logic needed for the current situation.

        query_by_id is a common function to where it will be included so that
            individual objects can be queried. Can be overwritten if required.
    """

    def __init__(self,
                 log_level: str | int=logging.INFO,
                 handler: logging.Handler=logging.StreamHandler(),
                 *args,
                 **kwargs) -> None:
        self.logger = log_factory(__name__, log_level, handler)
        self.logger.debug(f'Initialized {__class__}')

        self.query = Template('query all resources')

    def __str__(self) -> str:
        return self.query.template

    def string(self, *args, **kwargs) -> str:
        return self.query.template


class QueryTags(Query):
    def __init__(self,
                 namespace: str,
                 key: str,
                 cmp: str, # Cleanup compartment
                 log_level: str | int=logging.INFO,
                 handler: logging.Handler=logging.StreamHandler()):
        super().__init__(log_level=log_level, handler=handler)

        # Save template so only resource type and user are required at runtime
        self.query =  Template(
            "query $type resources where "
            f"definedTags.namespace = '{namespace}' && "
            f"definedTags.key = '{key}' && "
            "definedTags.value = '$user' && "
            "lifeCycleState != 'TERMINATED' && "
            "lifeCycleState != 'TERMINATING' && "
            f"compartmentid != '{cmp}'")

        self.logger.debug(f'Query: {self.query.template}')

    def string(self, type: str, user: str) -> str:        
        query =  self.query.substitute(type=type, user=user)
        self.logger.debug(f'{__name__} query: {query}')

        return query
    

class QueryCompartments(Query):
    def __init__(self, tag: str, key: str, log_level=logging.INFO) -> None:
        super().__init__(log_level=log_level)
        self.tag = tag
        self.key = key

        self.logger.debug(f'Key: {key}\n\tTag: {tag}')

    def string(self, **kwargs) -> str:
        """Keywork Arguments:
            compartments: list[str] = (Required) List of compartments to search
            resource: str = Resource type to search for
        """

        compartments = kwargs.get('compartments')
        if not compartments:
            raise QueryError('no compartment provided')
        
        query = (f"query {kwargs.get('resource', 'all')} resources where ")

        # Loop through compartments injecting OR as needed
        first = True
        for compartment in compartments:
            if first:
                query += f"compartmentId = '{compartment}' "
                first = False
            else:
                query += f" || compartmentId = '{compartment}' "

        self.logger.debug(f'{__name__} Query {query}')

        return query


class QueryError(Exception):
    def __init__(self, msg) -> None:
        self.error = msg

    def __str__(self) -> str:
        return f'exception QueryError raised: {self.error}'