import io
import os
import json

from modules import utils, router, handlers

log = utils.log_factory(__name__)

def handler(ctx, data: io.BytesIO = None):
    log.debug(json.dumps({
        'message': 'entered invoke handler'
    }))

    rtr = router.Router(os.getenv('IDM_URL'))
    rtr.register_route('/auth', handlers.AuthPage)
    rtr.register_route('/', handlers.MainPage)
    
    return rtr.route(ctx, data)
