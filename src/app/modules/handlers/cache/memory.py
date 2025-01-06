# Basic in-memory cache

from . import BaseCache

class MemCache(BaseCache):
    """MemCache is a class for in-memory caching. Currently does not support cache
       expiry, so it will cause memory leaks.
    """
    
    def __init__(self):
        super().__init__()

        self.cache = {}

    def get_session(self, session_id: str):
        return self.cache[session_id]

    def set_session(self, session_id: str, data) -> str:
        sid = self._generate_session_id()
        self.cache[sid] = data
        return sid
    
    def update_session(self, session_id: str, session_data):
        self.cache[session_id] = session_data
    
    def delete_session(self, session_id: str):
        return self.cache.pop(session_id)