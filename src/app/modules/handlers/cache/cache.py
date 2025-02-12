# Base Cache class to be overwritten by subclass

import secrets

from ...utils import log_factory

class BaseCache:
    """Base cache contains a session getter, setter, updater, and deleter. Implementation
       will be dependent on type of cache being utilized. CRUD methods should be
       overwritten. Token generation may be overwritten.

       Session IDs use the secrets library to return a randomized session token.
    """

    def __init__(self, *args, **kwargs):
        self.log = log_factory(__name__)

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

    def _generate_session_id(self, length: int=64) -> str:
        return secrets.token_urlsafe(length)
