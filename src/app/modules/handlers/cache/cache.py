# Base Cache class to be overwritten by subclass

import secrets

from collections.abc import Callable
from logging import Logger

class BaseCache:
    """Base cache contains a session getter, setter, updater, and deleter. Implementation
       will be dependent on type of cache being utilized. CRUD methods should be
       overwritten. Token generation may be overwritten.

       Session IDs use the secrets library to return a randomized session token.
    """

    def __init__(self, log_callable: Callable, **kwargs):
        self.log: Logger = log_callable(__name__)

    def __str__(self):
        return f'{self.__class__.__name__}'

    def get_session(self, session_id: str, *args, **kwargs) -> dict | None:
        self.log.warning('no cache initialized')
        return None

    def set_session(self, session_data: dict, *args, **kwargs) -> str:
        self.log.warning('no cache initialized')
        return self._generate_session_id()
    
    def update_session(self, session_id: str, session_data, *args, **kwargs):
        self.log.warning('no cache initialized')
    
    def delete_session(self, session_id: str, *args, **kwargs):
        self.log.warning('no cache initialized')

    def add_csrf(self, sid: str, n: int=1) -> list:
        self.log.warning('no cache initialized')
        tokens = []

        for _ in range(n):
            tokens.append(self._generate_csrf_token)

        return tokens

    def check_csrf(self, token: str, sid: str) -> bool:
        self.log.warning('no cache initialized')
        
        # No way to check without a cache
        return False

    def _generate_session_id(self, length: int=64) -> str:
        return secrets.token_urlsafe(length)
    
    def _generate_csrf_token(self) -> str:
        return secrets.token_urlsafe()
