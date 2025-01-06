# Redis cache compatible with OCI Cache service

import redis

from . import BaseCache

class RedisCache(BaseCache):
    def __init__(self, host: str, port: int=6379, expiry: int=3600, **kwargs):
        super().__init__()
        self.cache = redis.Redis(host=host,
                                 port=port,
                                 ssl=True,
                                 db=2,
                                 **kwargs)
        self.expiration = expiry

    def get_session(self, session_id: str) -> dict[bytes, bytes]:
        return self.cache.hgetall(session_id)

    def set_session(self, session_data: dict) -> str:
        sid = self._generate_session_id()
        self.cache.hset(sid, mapping=session_data)
        self.cache.expire(sid, self.expiration) # 1 hour expiry
        return sid
    
    def update_session(self, session_id: str, session_data: dict):
        self.cache.hset(session_id, mapping=session_data)
        self.cache.expire(session_id, self.expiration) # 1 hour expiry

    def delete_session(self, *session_id: str):
        self.cache.delete(*session_id)