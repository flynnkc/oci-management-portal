# Redis cache compatible with OCI Cache service

import json
import redis

from . import BaseCache

class RedisCache(BaseCache):
    def __init__(self, host: str, port: int=6379, expiry: int=3600, db: int=2,
                 **kwargs):
        super().__init__()
        self.cache = redis.Redis(host=host,
                                 port=port,
                                 ssl=True,
                                 db=db,
                                 **kwargs)
        self.expiration = expiry

        self.log.debug(json.dumps({'message': 'rediscache initialized',
                                   'host': host,
                                   'port': port,
                                   'db': db,
                                   'expiry': expiry}))

    def get_session(self, session_id: str) -> dict[bytes, bytes]:
        self.log.debug(json.dumps({'message': 'getting session',
                                   'session id': session_id}))
        return self.cache.hgetall(session_id)

    def set_session(self, session_data: dict) -> str:
        sid = self._generate_session_id()
        self.log.debug(json.dumps({'message': 'setting session',
                                   'session id': sid}))
        self.cache.hset(sid, mapping=session_data)
        self.cache.expire(sid, self.expiration) # 1 hour expiry
        return sid
    
    def update_session(self, session_id: str, session_data: dict):
        self.log.debug(json.dumps({'message': 'updating session',
                                   'session id': session_id}))
        self.cache.hset(session_id, mapping=session_data)
        self.cache.expire(session_id, self.expiration) # 1 hour expiry

    def delete_session(self, *session_id: str):
        self.log.warning(json.dumps({'message': 'deleting session',
                                     'session id': session_id}))
        self.cache.delete(*session_id)