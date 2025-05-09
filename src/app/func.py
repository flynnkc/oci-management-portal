import io
import json

from modules import environment, router, handlers

def handler(ctx, data: io.BytesIO = None):
    env = environment.Environment()
    log = env.log_factory(__name__)

    log.debug('Entered invoke handler')
    log.debug(f'Environment: {env}')
    log.debug(f'Signer: {vars(env.signer)}')

    rtr = router.Router(env)
    rtr.register_route('/', handlers.MainPage, env=env)
    
    return rtr.route(ctx, data)
