import os
import json
import base64

from . import authenticate
from fdk import context, response
from oci.secrets import SecretsClient
from oci.auth.signers import get_resource_principals_signer
from oci.exceptions import ServiceError

from .cache import BaseCache, RedisCache, MemCache
from ..utils import log_factory

ENV_CACHE = 'OCI_CACHE'

cache = ( RedisCache(os.getenv(ENV_CACHE)) if os.getenv(ENV_CACHE)
         else BaseCache() )

class BasePage:
    def __init__(self, **kwargs):
        self.log = log_factory(__name__)
        self.cache = cache

    def __str__(self):
        return f'{self.__class__.__name__}'

    def render(self, ctx: context.InvokeContext) -> response.Response:
        return response.Response(ctx,
                                headers={'Content-Type': 'text/html'},
                                response_data='<h1>Pass</h1>')
    

class AuthPage(BasePage):
    def __init__(self, idcs_url: str=os.getenv('IDM_URL'), redirect_url: str='/',
                **kwargs):
        super().__init__()
        self.idcs_url = idcs_url
        self.redirect_url = redirect_url

    def render(self, ctx: context.InvokeContext, **kwargs) -> response.Response:
        self.log.debug(json.dumps({
            'message': 'home handler invoked'
        }))

        signer = get_resource_principals_signer()
        config = {'region': signer.region, 'tenancy': signer.tenancy_id}

        client = SecretsClient(config, signer=signer)
        try:
            r = client.get_secret_bundle(os.getenv('APP_SECRET'))
        except ServiceError as e:
            self.log.error(json.dumps({
                'error': str(e),
                'message': 'error retrieving client id and secret'
            }))
            return response.Response(ctx,
                                    headers={'Content-Type': 'text/html'},
                                    response_data='<h1>500 - Internal Server Error</h1>',
                                    status_code=500)
        
        content = base64.b64decode(r.data.secret_bundle_content.content).decode()
        client_id, client_secret = content.split(':')

        token, key = authenticate.get_upst(
            self.idcs_url,
            ctx.HTTPHeaders()['access_tok'],
            client_id,
            client_secret
            )
        
        session_id = ctx.HTTPHeaders().get('sid')
        if session_id:
            # If user already has a session id update cache
            cache.update_session(session_id, {
                'token': token,
                'private_key': key
            })
        else:
            # Else cache new session
            session_id = cache.set_session({
                'token': token,
                'private_key': key
            })

        return response.Response(ctx,
                status_code=308,
                headers={'Location': self.redirect_url,
                            'Set-Cookie': f'sid={session_id}; Max-Age=3600; Secure'})


class MainPage(BasePage):
    def __init__(self):
        super().__init__()

    def render(self, ctx: context.InvokeContext, **kwargs) -> response.Response:
        return response.Response(ctx,
                                headers={'Content-Type': 'text/html'},
                                response_data='<h1>Pass</h1>')