import io
import os
import json
import base64

from fdk import context, response
from oci.util import to_dict
from oci.secrets import SecretsClient
from oci.auth.signers import get_resource_principals_signer
from oci.exceptions import ServiceError

from authenticate import get_security_token_signer
from ..utils import log_factory

log = log_factory(__name__)

def home(ctx: context.InvokeContext,
         idcs_url: str='',
         **kwargs) -> response.Response:
    log.debug(json.dumps({
        'message': 'home handler invoked'
    }))

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

    signer = get_security_token_signer(
        idcs_url,
        ctx.HTTPHeaders()['access_tok'],
        client_id,
        client_secret
        )

    return response.Response(ctx)

def page(ctx: context.InvokeContext, **kwargs) -> response.Response:
    return response.Response(ctx)