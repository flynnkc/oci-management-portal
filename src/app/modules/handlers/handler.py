import io
import os
import json
import base64

import authenticate

from fdk import context, response
from oci.secrets import SecretsClient
from oci.auth.signers import get_resource_principals_signer
from oci.exceptions import ServiceError

from cache import RedisCache
from ..utils import log_factory

log = log_factory(__name__)
cache = RedisCache(os.getenv('OCI_CACHE'))

# Ensure session is started then redirect to /p
def home(ctx: context.InvokeContext,
         idcs_url: str='',
         **kwargs) -> response.Response:
    log.debug(json.dumps({
        'message': 'home handler invoked'
    }))

    if 'sid' in ctx.HTTPHeaders():
        # If user already has a session pass through to page
        return response.Response(ctx,
            status_code=308,
            headers={'Location': '/p'})
    else:
        signer = get_resource_principals_signer()
        config = {'region': signer.region, 'tenancy': signer.tenancy_id}

        client = SecretsClient(config, signer=signer)
        try:
            r = client.get_secret_bundle(os.getenv('APP_SECRET'))
        except ServiceError as e:
            log.error(json.dumps({
                'error': e,
                'message': 'error retrieving client id and secret'
            }))
            return response.Response(ctx, status_code=500)
        
        content = base64.b64decode(r.data.secret_bundle_content.content).decode()
        client_id, client_secret = content.split(':')

        token, key = authenticate.get_upst(
            idcs_url,
            ctx.HTTPHeaders()['access_tok'],
            client_id,
            client_secret
            )
        
        session_id = cache.set_session({
            'token': token,
            'private_key': key
        })

        return response.Response(ctx,
                status_code=308,
                headers={'Location': '/p',
                         'Set-Cookie': f'sid={session_id}; HttpOnly; Max-Age=3600; Secure'})

def page(ctx: context.InvokeContext, **kwargs) -> response.Response:
    return response.Response(ctx)