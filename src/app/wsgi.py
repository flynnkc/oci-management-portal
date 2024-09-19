#!/usr/bin/python3.11

from cachelib import FileSystemCache
from datetime import timedelta
from flask import Flask
from flask_session import Session
import logging
from oci.config import DEFAULT_LOCATION, DEFAULT_PROFILE
from os import getenv

from modules import add_handlers, Configuration

### Globals
TIMEOUT_IN_SECONDS = 900 # 10 minute session timeout
PREFIX = 'OCIDOMAIN' # Environment variable prefix

# What to do about these? Refactor.
idm_endpoint = getenv(f'{PREFIX}_IDM_ENDPOINT')
idm_client = getenv(f'{PREFIX}_CLIENT_ID')
app_host = getenv(f'{PREFIX}_APP_URI')
auth_type = getenv(f'{PREFIX}_AUTH_TYPE')
oci_profile = getenv(f'{PREFIX}_PROFILE', DEFAULT_PROFILE)
oci_location = getenv(f'{PREFIX}_LOCATION', DEFAULT_LOCATION)
search_namespace = getenv(f'{PREFIX}_TAG_NAMESPACE')
search_tag = getenv(f'{PREFIX}_TAG_KEY')
filter_namespace = getenv(f'{PREFIX}_FILTER_NAMESPACE', search_namespace)
filter_tag = getenv(f'{PREFIX}_FILTER_KEY')

def app(*args, **kwargs) -> Flask:
    '''Flask app factory
       Run flask with flask -A "wsgi:app([file='sample.ini'])" [--debug]
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

    add_handlers(app, cfg)

    # Gunicorn logging hack TODO find a better way to set log level
    if __name__ != '__main__' and app.logger.getEffectiveLevel() != logging.DEBUG:
        gl = logging.getLogger('gunicorn.error')
        app.logger.setLevel(gl.getEffectiveLevel())

    return app
