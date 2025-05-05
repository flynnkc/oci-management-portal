import os
import logging

from oci.auth.signers import get_resource_principals_signer

import search
from cache import RedisCache

# Environment variables
ENV_LOG_LEVEL = 'LOG_LEVEL'
ENV_CACHE = 'OCI_CACHE'
ENV_SECRET = 'APP_SECRET'
ENV_IDM = 'IDM_URL'

# Tags environment variables
ENV_TNS = 'TAG_NAMESPACE'
ENV_TKEY = 'TAG_KEY'
ENV_FNS = 'FILTER_NAMESPACE'
ENV_FKEY = 'FILTER_KEY'

class Environment:
    
    def __init__(self):
        self.log_level = os.getenv(ENV_LOG_LEVEL, logging.INFO)
        self.log_handler = None
        self.cache = RedisCache(os.getenv(ENV_CACHE))

        # Tag variables
        self.tag_namespace = os.getenv(ENV_TNS) # Namespace to ID ownership
        self.tag_key = os.getenv(ENV_TKEY) # Tag key should be owner ID
        # Set filter namespace if present else use tag namespace
        self.filter_namespace = (os.getenv(ENV_FNS) if os.getenv(ENV_FNS)
            else self.tag_namespace)
        self.filter_key = os.getenv(ENV_FKEY)

        # OCI signer
        self.signer = get_resource_principals_signer()

        # OCI Service Clients
        self.search = search.Search(self.tag_namespace, self.tag_key,
                                    self.log_factory('Search'), signer=self.signer)
        self.search.set_filter(search.ExpiryFilter(self.filter_namespace,
                                            self.filter_key,
                                            logger=self.log_factory('ExpiryFilter')))

    def __str__(self):
        return f'{self.__class__}:{self.__dict__}'

    def log_factory(self, name: str, **kwargs) -> logging.Logger:
        logger = logging.getLogger(name)
        logger.handlers.clear()
        
        # StreamHandler as default
        if not self.log_handler: log_handler = logging.StreamHandler()

        logger.addHandler(log_handler)
        logger.setLevel(self.log_level)

        return logger
