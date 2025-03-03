import os
import jinja2

from fdk import context, response

from .tokens import AuthenticationError, authenticate, get_claim_sub
from .cache import BaseCache, RedisCache
from ..utils import log_factory

ENV_CACHE = 'OCI_CACHE'

cache = ( RedisCache(os.getenv(ENV_CACHE)) if os.getenv(ENV_CACHE)
         else BaseCache() )


class BasePage:
    def __init__(self, **kwargs):
        self.log = log_factory(__name__)
        self.cache = cache
        self.env = jinja2.Environment(
            loader=jinja2.PackageLoader('func'),
            autoescape=jinja2.select_autoescape(),
            auto_reload=False
        )

    def __str__(self):
        return f'{self.__class__}:{self.__dict__}'

    def render(self, ctx: context.InvokeContext) -> response.Response:
        return response.Response(ctx,
                                headers={'Content-Type': 'text/html'},
                                response_data='<h1>Pass</h1>')
    
    def _internal_server_error(self, ctx) -> response.Response:
        return response.Response(ctx,
                                headers={'Content-Type': 'text/html'},
                                status_code=500,
                                response_data='<h1>Internal Server Error</h1>')
    
    def _unauthorized_error(self, ctx) -> response.Response:
        return response.Response(ctx,
                                headers={'Content-Type': 'text/html'},
                                status_code=401,
                                response_data='<h1>Unauthorized</h1>')


class MainPage(BasePage):
    def __init__(self):
        super().__init__()

    def render(self, ctx: context.InvokeContext, **kwargs) -> response.Response:
        req_headers = ctx.HTTPHeaders()
        resp_headers = {'Content-Type': 'text/html'}

        # No headers but do have access token
        if not req_headers.get('sid') and req_headers.get('at'):
            try:
                at = req_headers.get('at')
                user_data = authenticate(req_headers.get('host'), at)
                user_data['sub'] = get_claim_sub(at)
            except AuthenticationError as e:
                self.log.error(f'an exception occurred during authentication: {e}')
                self.log.debug(f'exception request data: {e.data}')
                return self._internal_server_error(ctx)

            session_id = self.cache.set_session(user_data)
            resp_headers.update({'Set-Cookie': f'sid={session_id}; Max-Age=3600; Secure'})

        # Have session will travel
        elif req_headers('sid'):
            user_data = self.cache.get_session(req_headers.get('sid'))

        # No session no token no luck
        else:
            return self._unauthorized_error(ctx)

        if ctx.Method() == 'GET':
            template = self.env.get_template('index.html')
            resp_data = template.render(user=user_data['sub'])

            return response.Response(ctx,
                                     headers=resp_headers,
                                     response_data=resp_data)


        return self._internal_server_error(ctx)
    