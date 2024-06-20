#!/usr/bin/python3.11

from oci import resource_search

from oci.config import from_file
from oci.signer import Signer

class Search:
    def __init__(self, config: dict, signer: Signer=None):
        self.config = config
        self.signer = signer
        self.client = resource_search.ResourceSearchClient(config, signer=signer)