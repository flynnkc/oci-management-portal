# Basic in-memory cache

import json

from . import BaseCache

class MemCache(BaseCache):
    """MemCache is a class for in-memory caching. Currently does not support cache
       expiry, so it will cause memory leaks. Thankfully, this is intended to run
       in a serverless function, so will be dumped regularly preventing memory
       usage.
    """
    
    def __init__(self):
        super().__init__()

        self.cache = {}

        self.log.debug(json.dumps({'message': 'memcache initialized'}))

    def get_session(self, session_id: str):
        self.log.debug(json.dumps({'message': 'getting session',
                                   'session id': session_id}))
        return self.cache.get(session_id)

    def set_session(self, session_id: str, data) -> str:
        sid = self._generate_session_id()
        self.cache[sid] = data
        self.log.debug(json.dumps({'message': 'setting session',
                                   'session id': session_id}))
        return sid
    
    def update_session(self, session_id: str, session_data):
        self.log.debug(json.dumps({'message': 'updating session',
                                   'session id': session_id}))
        self.cache[session_id] = session_data
    
    def delete_session(self, session_id: str):
        self.log.warning(json.dumps({'message': 'deleting session',
                                   'session id': session_id}))
        return self.cache.pop(session_id)