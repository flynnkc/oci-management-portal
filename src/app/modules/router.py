import io
import json
import utils

from urllib.parse import urlparse

from fdk import context, response
from modules import handlers

class Router:
    def __init__(self, idcs_url: str, handler=None, **kwargs):
        self.idcs_url = idcs_url
        self.routes = {
            '/': handlers.home,
            'p': handlers.page
        }
        self.log = utils.log_factory(__name__, handler=handler, **kwargs)
        self.log.debug(json.dumps({
            'message': 'router initialized',
            'idm': idcs_url,
            'handler': handler,
            'routes': self.routes.keys()
        }))

    def route(self, ctx: context.InvokeContext,
              data: io.BytesIO | None) -> response.Response:
        self.log.debug(json.dumps({
            'Headers': ctx.HTTPHeaders,
            'Method': ctx.Method(),
            'URL': ctx.RequestURL(),
            'Data': data.read().decode('utf-8')
        }))

        url = urlparse(ctx.RequestURL())
        self.log.debug(json.dumps({
            'parsed_url': url
        }))

        if not url.path.split('/')[1]:
            # No path given, assuming path='/'
            return self.routes['/'](ctx)
        else:
            try:
                return self.routes[url.path.split('/')](ctx)
            except KeyError:
                self.log.warning(json.dumps({
                    'message': 'unable to find route',
                    'url': url
                }))
                return response.Response(ctx, status_code=404)
            except Exception as e:
                self.log.error(json.dumps({
                    'error': e,
                    'message': 'error trying to find route',
                    'url': url
                }))
                return response.Response(ctx, status_code=500)
    