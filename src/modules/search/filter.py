#!/usr/bin/python3.11

import datetime
import logging
from oci.response import Response


class AbstractFilter:
    def __init__(self, **kwargs):
        log_level = kwargs.get('log_level', logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        handler = logging.StreamHandler()
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))

        
        if not self.logger.handlers:
            self.logger.addHandler(handler)

    def __repr__(self) -> str:
        return f'AbstractFilter - log_level: {self.logger.getEffectiveLevel()}'


    def results(self, response: Response, **kwargs):
        return response


# Filter resources based on expiry date tag
class ExpiryFilter(AbstractFilter):
    def __init__(self, tag: str, key: str, log_level=logging.INFO, **kwargs):
        super().__init__(log_level=log_level)
        self.tag = tag
        self.key = key
        self.logger.debug(f'Using Expiry Filter: {self}')

    def __repr__(self) -> str:
        return (
            f'ExpiryFilter - log_level: {self.logger.getEffectiveLevel()}\n'
            f'\tTag: {self.tag}\n'
            f'\tKey: {self.key}\n'
        )

    def results(self, response: Response, **kwargs):
        today = datetime.date.today()
        self.logger.debug(f'Today: {today}')

        
        # Updated Logic for Filter
        for i in range(len(response.data.items) - 1, -1, -1):
            item = response.data.items[i]
            try:
                expiry_str = item.defined_tags[self.tag][self.key]
                expiry_date = datetime.datetime.strptime(
                    expiry_str, '%Y-%m-%d'
                ).date()

                # If expiry is in the future, REMOVE the resource
                if today <= expiry_date:
                    del response.data.items[i]

            # Keep items with missing or invalid tags
            except (KeyError, ValueError):
                pass

        return response

