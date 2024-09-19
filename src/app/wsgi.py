#!/usr/bin/python3.11

from cachelib import FileSystemCache
from datetime import timedelta
from flask import Flask
from flask_session import Session
import logging

from modules import add_handlers, Configuration

### Globals
TIMEOUT_IN_SECONDS = 900 # 10 minute session timeout


def app(*args, **kwargs) -> Flask:
    '''Flask app factory
       Run flask with flask -A "wsgi:app([file='sample.ini', prefix='foo'])" [--debug]
       Run Gunicorn with gunicorn "wsgi:app([file='sample.ini', prefix='foo']")
    '''
    # Create application config
    cfg = Configuration(**kwargs)

    # Flask
    app = Flask(__name__)
    app.config['SESSION_COOKIE_NAME'] = 'omid'
    app.config['SESSION_TYPE'] = 'cachelib'
    # FileSystemCache is a cachelib local filesystem cache, saves sessions to ./session
    app.config['SESSION_CACHELIB'] = FileSystemCache('session',
                                                    default_timeout=TIMEOUT_IN_SECONDS)
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=TIMEOUT_IN_SECONDS)
    Session(app) # Using local filesystem session cache

    # Gunicorn logging hack TODO find a better way to set log level
    if __name__ != '__main__' and app.logger.getEffectiveLevel() != logging.DEBUG:
        gl = logging.getLogger('gunicorn.error')
        app.logger.setLevel(gl.getEffectiveLevel())

    app.logger.debug(cfg)
    app = add_handlers(app, cfg)

    return app

if __name__ == '__main__':
    app = app()
    app.run()