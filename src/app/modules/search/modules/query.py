#!/usr/pyton3.11

import logging


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

    def __init__(self, log_level=logging.INFO):
        # Logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        handler = logging.StreamHandler()
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
        self.logger.addHandler(handler)
        self.logger.debug(f'Initialized {__class__}')

    def query(self) -> str :
        return "query all resources"
    
    def query_by_id(self, ocid: str) -> str:
        query = f"query all resources where identifier = '{ocid}'"
        self.logger.debug(f'{__name__} called returning query {query}')

        return query
    

class QueryTags(Query):
    def __init__(self, tag: str, key: str, log_level=logging.INFO):
        super().__init__(log_level=log_level)
        self.tag = tag
        self.key = key

        self.logger.debug(f'Key: {key}\n\tTag: {tag}')

    def query(self, **kwargs):
        """Keword arguments:
            user: str = (Required) Username for search
            resource: str = Resource type to search for
        """
        user = kwargs.get('user')
        if not user:
            raise QueryError
        
        query =  (f"query {kwargs.get('resource', 'all')} resources where "
            f"definedTags.namespace = '{self.tag}' && definedTags.key = "
            f"'{self.key}' && definedTags.value = '{user}' && lifeCycleState "
            "!= 'TERMINATED' && lifeCycleState != 'TERMINATING'")
        self.logger.debug(f'{__name__} query: {query}')

        return query
    

class QueryCompartments(Query):
    def __init__(self, tag: str, key: str, log_level=logging.INFO):
        super().__init__(log_level=log_level)
        self.tag = tag
        self.key = key

        self.logger.debug(f'Key: {key}\n\tTag: {tag}')

    def query(self, **kwargs):
        """Keywork Arguments:
            compartments: list[str] = (Requried) List of compartments to search
            resource: str = Resource type to search for
        """

        compartments = kwargs.get('compartments')
        if not compartments:
            raise QueryError
        
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
    def __init__(self, error):
        self.error = error

    def __str__(self):
        return(repr(self.error))