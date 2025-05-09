#!/usr/bin/python3.11

import datetime
import logging

from collections.abc import Callable

from oci.response import Response

# Used to filter search results
class AbstractFilter:
    def __init__(self, *args, **kwargs):
        pass

    def __repr__(self) -> str:
        return f'AbstractFilter'

    # The filter function takes a response and returns a response.
    # This method is meant to be overwritten.
    def results(self, response: Response, **kwargs):
        return response
    
# Check for expiring resources. Takes keyword arguments for timedelta. A resource
# that should be defaulted to a 90 day expiry should be entered as (days=90).
class ExpiryFilter(AbstractFilter):
    def __init__(self, log_callable: Callable, tag_namespace: str, tag_key: str,
                 **kwargs):
        super().__init__()
        self.logger: logging.Logger = log_callable(__name__)
        self.tag = tag_namespace
        self.key = tag_key
        self.logger.debug(f'Using Expiry Filter: {self}')

    def __repr__(self) -> str:
        return (f'ExpiryFilter - log_level: {self.logger.getEffectiveLevel()}\n'
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