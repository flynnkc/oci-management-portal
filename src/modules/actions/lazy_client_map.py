#!/usr/bin/python3.11

from collections.abc import Callable
from typing import Any


class LazyClientMap(dict):
    def __init__(self, allowed_regions, factory: Callable[[str], Any]):
        super().__init__()
        self.allowed_regions = set(allowed_regions or [])
        self.factory = factory

    def __contains__(self, region):
        return dict.__contains__(self, region) or region in self.allowed_regions

    def __missing__(self, region):
        if self.allowed_regions and region not in self.allowed_regions:
            raise KeyError(region)
        client = self.factory(region)
        self[region] = client
        return client
