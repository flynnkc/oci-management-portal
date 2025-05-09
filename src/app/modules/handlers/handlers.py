#from urllib.parse import urlparse, parse_qs

import jinja2

from fdk import context, response
from oci.util import to_dict
from oci.auth.signers import SecurityTokenSigner

from .authenticate import Authenticator, AuthenticationError
from .cache import OciCache
from .search import Search, ExpiryFilter
from ..environment import Environment


class BasePage:
    def __init__(self, env: Environment=Environment(), **kwargs):
        self.log = env.log_factory(__name__)
        self.log_callable = env.log_factory
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
    def __init__(self, env: Environment=Environment(), **kwargs):
        super().__init__(env)

        # Instance variables
        self.tag_ns = env.tag_namespace
        self.tag_key = env.tag_key
        self.filter_ns = env.filter_namespace
        self.filter_key = env.filter_key

        self.region = env.region
        self.tenancy_id = env.tenancy_id

        # Set up classes
        self.auth = Authenticator(env.log_factory, env.idm_url, env.secret,
                                  signer=env.signer, passwd=env.key_passwd)
        self.cache = OciCache(env.cache, env.log_factory, port=env.cache_port,
                              expiry=env.cache_expiry, db=env.cache_db)

        #self.search = Search(env)
        #self.search.set_filter(ExpiryFilter(env))

    def render(self, ctx: context.InvokeContext, **kwargs) -> response.Response:
        self.ctx = ctx

        # Get request headers to inspect
        req_headers = ctx.HTTPHeaders()

        # No headers but do have access token
        if not req_headers.get('sid') and req_headers.get('at'):
            try:
                at = req_headers.get('at')
                self.user_data = self.auth.authenticate(at)
                self.user_data['sub'] = self.auth.get_claim_sub(at)
            except AuthenticationError as e:
                self.log.error(f'an exception occurred during authentication: {e}')
                self.log.debug(f'exception request data: {e.data}')
                return self.internal_server_error(ctx)

            session_id = self.cache.set_session(self.user_data)
            self.resp_headers.update({'Set-Cookie': f'sid={session_id}; Max-Age=3600; Secure'})

        # Have session will travel
        elif req_headers.get('sid'):
            self.user_data = self.cache.get_session(req_headers.get('sid'))

        # No session no token no luck
        else:
            return self.unauthorized_error(ctx)
        
        self.log.debug(f'User data: {self.user_data}')

        # Define behavior based on request method
        if ctx.Method() == 'GET':
            return self.get()

        return self.internal_server_error(ctx)
    
    # GET request to search for resources
    def get(self) -> response.Response:
        signer = SecurityTokenSigner(self.user_data['token'],
                                     self.auth.load_private_pem(
                                         self.user_data['key']))
        self.log.debug(f'Signer created: {signer} - {dir(signer)}')
        search = Search(self.log_callable, self.tag_ns, self.tag_key, signer,
                        self.region, self.tenancy_id, filter=ExpiryFilter(
                            self.log_callable, self.filter_ns, self.filter_key
                        ))
        
        # Load main page
        search_data = search.get_user_resources(self.user_data['sub'],
                                                        limit=1000)
        template = self.templates.get_template('index.html')
        resp_data = template.render(user=self.user_data['sub'],
                                    items=to_dict(search_data.data)['items'],
                                    regions=search.region_names,
                                    home=search.home_region,
                                    selections=search.resource_list)

        return response.Response(self.ctx,
                                    headers=self.resp_headers,
                                    response_data=resp_data)

    def post(self) -> response.Response:
        pass
    