# Base Cache class to be overwritten by subclass

import secrets

class BaseCache:
    """Base cache contains a session getter, setter, updater, and deleter. Implementation
       will be dependent on type of cache being utilized. CRUD methods should be
       overwritten. Token generation may be overwritten.

       Session IDs use the secrets library to return a randomized session token.
    """

    def __init__(self, *args, **kwargs):
        pass

    def __str__(self):
        return f'{self.__class__.__name__}'

    def get_session(self, session_id: str, *args, **kwargs):
        pass

    def set_session(self, session_data: dict, *args, **kwargs):
        pass
    
    def update_session(self, session_id: str, session_data, *args, **kwargs):
        pass
    
    def delete_session(self, session_id: str, *args, **kwargs):
        pass

    def _generate_session_id(self, length: int=64):
        return secrets.token_urlsafe(length)
