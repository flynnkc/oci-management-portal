# Redis cache compatible with OCI Cache service

import json
import redis

from . import BaseCache

class OciCache(BaseCache):

    CSRF_KEY = 'csrf'

    def __init__(self, host: str, port: int=6379, expiry: int=3600, db: int=2,
                 **kwargs):
        super().__init__()
        self.cache = redis.Redis(host=host,
                                 port=port,
                                 ssl=True,
                                 db=db,
                                 decode_responses=True,
                                 **kwargs)
        self.expiration = expiry
        self.expiration_ms = expiry * 1000

        self.log.debug(json.dumps({'message': 'rediscache initialized',
                                   'host': host,
                                   'port': port,
                                   'db': db,
                                   'expiry': expiry}))

    def get_session(self, session_id: str) -> dict:
        self.log.debug(json.dumps({'message': 'getting session',
                                   'session id': session_id}))
        return self.cache.hgetall(session_id)

    def set_session(self, session_data: dict) -> str:
        sid = self._generate_session_id()
        # Pipeline to send multiple transactions in a single trip
        pipe = self.cache.pipeline()
        self.log.debug(json.dumps({'message': 'setting session',
                                   'session id': sid}))
        pipe.hset(sid, mapping=session_data)
        pipe.expire(sid, self.expiration) # 1 hour expiry
        pipe.execute()
        return sid
    
    def update_session(self, session_id: str, session_data: dict):
        self.log.debug(json.dumps({'message': 'updating session',
                                   'session id': session_id}))
        self.cache.hset(session_id, mapping=session_data)

    def delete_session(self, *session_id: str):
        self.log.warning(json.dumps({'message': 'deleting session',
                                     'session id': session_id}))
        self.cache.delete(*session_id)

    # add_csrf creates CSRF tokens associated with session and returns token list
    def add_csrf(self, sid: str, n: int=1) -> list:
        """CSRF tokens in tokens field with mapping:
            {'token1': 'session id',
             'token2': 'session id'}
        """

        tokens = {}
        for _ in range(n):
            tokens[self._generate_csrf_token] = sid

        pipe = self.cache.pipeline()
        pipe.hset(self.CSRF_KEY, mapping=tokens)
        # set expirations on each key in tokens dict
        pipe.hpexpire(self.CSRF_KEY, self.expiration_ms, *tokens.keys(), nx=True)
        pipe.execute()

        return list(tokens.keys())

    # check_csrf gets and removes the requested token, checking it against the
    # provided session ID
    def check_csrf(self, token: str, sid: str) -> bool:
        pipe = self.cache.pipeline()

        pipe.hget(self.CSRF_KEY, token)
        pipe.hdel(self.CSRF_KEY, token)
        r = pipe.execute()

        # r[0] returns value that should be session id for user
        if r[0] == sid:
            return True
        
        return False