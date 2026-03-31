#!/usr/bin/python3.11

from cachelib import FileSystemCache
from datetime import timedelta
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_session import Session

from modules import add_handlers, Configuration

### Globals
TIMEOUT_IN_SECONDS = 900 # 10 minute session timeout


def create_app(*args, **kwargs) -> Flask:
    """Flask app factory
       Run flask with flask -A "wsgi:app([prefix='foo'])" run [--debug]
       Run Gunicorn with gunicorn -c gunicorn.config.py "wsgi:app([prefix='foo']")
    """
    # Create application config
    cfg = Configuration(**kwargs)

    # Flask
    app = Flask(__name__, static_folder='static')

    # Session configuration
    app.config['SESSION_COOKIE_NAME'] = 'omid'
    app.config['SESSION_TYPE'] = 'cachelib'
    # FileSystemCache is a cachelib local filesystem cache, saves sessions to ./session
    app.config['SESSION_CACHELIB'] = FileSystemCache('session',
                                                    default_timeout=TIMEOUT_IN_SECONDS)
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=TIMEOUT_IN_SECONDS)
    Session(app) # Using local filesystem session cache

    # Flask Logging
    app.logger.setLevel(cfg.get_log_level())
    app.logger.addHandler(cfg.get_log_handler())
    app.logger.debug(cfg)
    if cfg.get_proxy():
        # Honor original scheme/host information from the trusted proxy so
        # url_for(..., _external=True) generates HTTPS callbacks when TLS is
        # terminated upstream. We limit ProxyFix to a single hop because the
        # ingress/load balancer should be the only proxy in front of the app.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
        app.config.setdefault('PREFERRED_URL_SCHEME', 'https')

    app = add_handlers(app, cfg)

    return app


app = create_app()
