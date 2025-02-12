import io
import json

from collections.abc import Callable
from urllib.parse import urlparse

from fdk import context, response
from . import log_factory

class Router:
    """Router contains routes to associate handlers for controller logic.
    """
    def __init__(self, idcs_url: str, handler=None, **kwargs):
        self.routes = {}
        self.log = log_factory(__name__, handler=handler, **kwargs)
        self.log.debug(json.dumps({
            'message': 'router initialized',
            'idm': idcs_url,
            'handler': handler
        }))

    def route(self, ctx: context.InvokeContext,
              data: io.BytesIO | None) -> response.Response:
        self.log.debug(json.dumps({
            'Headers': ctx.HTTPHeaders(),
            'Method': ctx.Method(),
            'URL': ctx.RequestURL(),
            'Data': data.read().decode('utf-8')
        }))

        url = urlparse(ctx.RequestURL())
        self.log.debug(json.dumps({
            'parsed_url': url,
            'parsed netloc': url.netloc,
            'parsed path': url.path,
            'parsed params': url.params,
            'parsed query': url.query
        }))

        try:
            return self.routes[url.path].render(ctx)
        except KeyError:
            self.log.warning(json.dumps({
                'message': 'unable to find route',
                'url': url.path,
                'registered routes': list(self.routes.keys())
            }))
            return response.Response(ctx,
                                        headers={'Content-Type': 'text/html'},
                                        response_data='<h1>404</h1>',
                                    status_code=404)
        except Exception as e:
            self.log.error(json.dumps({
                'error': e,
                'message': 'error trying to find route',
                'url': url
            }))
            return response.Response(ctx, status_code=500)
            
    def register_route(self, path: str, handler: Callable, **kwargs):
        self.routes[path] = handler(**kwargs)
        self.log.debug(f'registered routes: {self.routes}')
    