#!/usr/bin/python3.11

import datetime
import logging

from oci.response import Response

# Used to filter search results
class AbstractFilter:
    def __init__(self, **kwargs):
        log_level = kwargs.get('log_level', logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        handler = logging.StreamHandler()
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
        self.logger.addHandler(handler)

    def __repr__(self) -> str:
        f'AbstractFilter - log_level: {self.logger.getEffectiveLevel}'

    # The filter function takes a response and returns a response.
    # This method is meant to be overwritten.
    def results(self, response: Response, **kwargs):
        return response
    
# Check for expiring resources. Takes keyword arguments for timedelta. A resource
# that should be defaulted to a 90 day expiry should be entered as (days=90).
class ExpiryFilter(AbstractFilter):
    def __init__(self, tag:str, key: str, log_level=logging.INFO, **kwargs):
        super().__init__(log_level=log_level)
        self.tag = tag
        self.key = key
        self.logger.debug(f'Using Expiry Filter: {self}')

    def __repr__(self) -> str:
        return (f'ExpiryFilter - log_level: {self.logger.getEffectiveLevel}\n'
                f'\tTag: {self.tag}\n\tKey: {self.key}\n')

    def results(self, response: Response, **kwargs):
        today = datetime.date.today()
        self.logger.debug(f'Today: {today}')

        for i, item in enumerate(response.data.items):
            try:
                # If today is before expiry tag, remove item
                if today <= datetime.datetime.strptime(
                    item.defined_tags[self.tag][self.key], '%Y-%m-%d').date():
                    del response.data.items[i]
            # Retain untagged items
            except (KeyError, ValueError):
                pass

        return response