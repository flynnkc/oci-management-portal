#!/usr/bin/python3.11

import datetime
import logging
from oci.response import Response
from ..utils import log_factory


class AbstractFilter:
    def __init__(self,
                 handler: logging.Handler=logging.StreamHandler(),
                 log_level: int | str = logging.INFO,
                 **kwargs) -> None:
        self.logger = log_factory(__name__, log_level, handler)

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
        self.logger.debug(f'running results with current date: {today}')

        
        # Updated Logic for Filter
        for i in range(len(response.data.items) - 1, -1, -1):
            item = response.data.items[i]
            try:
                expiry_str = item.defined_tags[self.tag][self.key]
                expiry_date = datetime.datetime.strptime(
                    expiry_str, '%Y-%m-%d'
                ).date()
                self.logger.debug(f'expiry date on {item.identifier}: {expiry_date}')

                # If expiry is in the future, REMOVE the resource
                if today <= expiry_date:
                    self.logger.debug(f'removing item {item.identifier} from results')
                    del response.data.items[i]

            # Keep items with missing or invalid tags
            except (KeyError, ValueError) as e:
                self.logger.warning('exception occurred on resource '
                                    f'{item.identifier}: {e}')

        return response

