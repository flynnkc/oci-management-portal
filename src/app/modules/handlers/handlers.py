from urllib.parse import urlparse, parse_qs

import jinja2

from fdk import context, response
from oci.util import to_dict

from .tokens import AuthenticationError, authenticate, get_claim_sub
from ..environment import Environment


class BasePage:
    def __init__(self, env: Environment, **kwargs):
        self.cache = env.cache
        self.search = env.search
        self.log = env.log_factory(__name__)
        self.templates = jinja2.Environment(
            loader=jinja2.PackageLoader('func'),
            autoescape=jinja2.select_autoescape(),
            auto_reload=False
        )

        # Render variables
        self.resp_headers = {'Content-Type': 'text/html'}
        self.ctx: context.InvokeContext = None
        self.user_data: dict = {}

    def __str__(self):
        return f'{self.__class__}:{self.__dict__}'

    def render(self, ctx: context.InvokeContext) -> response.Response:
        return response.Response(ctx,
                                headers={'Content-Type': 'text/html'},
                                response_data='<h1>Pass</h1>')
    
    def internal_server_error(self, ctx) -> response.Response:
        return response.Response(ctx,
                                headers={'Content-Type': 'text/html'},
                                status_code=500,
                                response_data='<h1>Internal Server Error</h1>')
    
    def unauthorized_error(self, ctx) -> response.Response:
        return response.Response(ctx,
                                headers={'Content-Type': 'text/html'},
                                status_code=401,
                                response_data='<h1>Unauthorized</h1>')


class MainPage(BasePage):
    def __init__(self, env: Environment, **kwargs):
        super().__init__(env)

    def render(self, ctx: context.InvokeContext, **kwargs) -> response.Response:
        self.ctx = ctx

        req_headers = ctx.HTTPHeaders()

        # No headers but do have access token
        if not req_headers.get('sid') and req_headers.get('at'):
            try:
                at = req_headers.get('at')
                user_data = authenticate(req_headers.get('host'), at)
                user_data['sub'] = get_claim_sub(at)
            except AuthenticationError as e:
                self.log.error(f'an exception occurred during authentication: {e}')
                self.log.debug(f'exception request data: {e.data}')
                return self.internal_server_error(ctx)

            session_id = self.cache.set_session(user_data)
            self.resp_headers.update({'Set-Cookie': f'sid={session_id}; Max-Age=3600; Secure'})

        # Have session will travel
        elif req_headers.get('sid'):
            self.user_data = self.cache.get_session(req_headers.get('sid'))

        # No session no token no luck
        else:
            return self.unauthorized_error(ctx)

        if ctx.Method() == 'GET':
            return self.get()

        return self.internal_server_error(ctx)
    
    def get(self) -> response.Response:
        # Load main page
        search_data = self.search.get_user_resources(self.user_data['sub'],
                                                        limit=1000)
        template = self.templates.get_template('index.html')
        resp_data = template.render(user=self.user_data['sub'],
                                    items=to_dict(search_data.data)['items'],
                                    regions=self.search.region_names,
                                    home=self.search.home_region,
                                    selections=self.search.resource_list)

        return response.Response(self.ctx,
                                    headers=self.resp_headers,
                                    response_data=resp_data)

    def post(self) -> response.Response:
        pass
    