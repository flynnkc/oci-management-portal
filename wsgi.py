#!/usr/bin/python3.11

from authlib.integrations.flask_client import OAuth
from cachelib import FileSystemCache
from datetime import timedelta
from flask import Flask, session, redirect, render_template, url_for, request
from flask_session import Session
from os import getenv
from oci.util import to_dict
from werkzeug import exceptions

from modules import create_signer
from modules.search import Search

### Globals
TIMEOUT_IN_SECONDS = 900
PREFIX = 'OCIDOMAIN'
idm_host = getenv(f'{PREFIX}_IDM_ENDPOINT')
app_host = getenv(f'{PREFIX}_APP_URI')

app = Flask(__name__)
app.config['SESSION_COOKIE_NAME'] = 'omid'
app.config['SESSION_TYPE'] = 'cachelib'
# FileSystemCache is a cachelib local filesystem cache, saves sessions to ./session
app.config['SESSION_CACHELIB'] = FileSystemCache('session',
                                                 default_timeout=TIMEOUT_IN_SECONDS)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=TIMEOUT_IN_SECONDS)
Session(app) # Using local filesystem session cache

# OCI SDK Authentication
cfg, signer = create_signer(getenv(f'{PREFIX}_AUTH_TYPE'),
                            profile=getenv(f'{PREFIX}_PROFILE'),
                            location=getenv(f'{PREFIX}_LOCATION'))

# Search
search = Search(
    getenv(f'{PREFIX}_TAG_NAMESPACE'),
    getenv(f'{PREFIX}_TAG_KEY'),
    cfg,
    signer=signer,
    log_level=app.logger.getEffectiveLevel())

# OIDC
oauth = OAuth(app)
oauth.register(
    'ocidomain',
    client_id=getenv(f'{PREFIX}_CLIENT_ID'),
    client_secret=getenv(f'{PREFIX}_CLIENT_SECRET'),
    server_metadata_url=f'{idm_host}/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid'})

### Handlers

# Homepage handler
@app.route('/', methods=['GET'])
def home():
    if session.get('user'):
        results = search.get_user_resources(session.get('user')['sub'])
        items = to_dict(results.data)['items']
        app.logger.debug(f'Items returned for user {session.get("user")["sub"]}:\t{items}')

        return render_template('index.html',
                               name=session.get('user')['sub'],
                               items=items,
                               next_page=results.next_page)
    
    return render_template('index.html')

# Pagination support using HTMX
@app.route('/p', methods=['GET'])
def pagination():
    results = search.get_user_resources(
        session.get('user')['sub'],
        page=request.args.get('next_page', None))
    items = to_dict(results.data)['items']
    
    return render_template('snippet-card.html',
                           items=items,
                           next_page=results.next_page)

# OpenID Connect Sign in via OCI IAM Identity Domain Provider
@app.route('/login', methods=['GET'])
def login():
    if not session.get('user'):
        uri = url_for('callback', _external=True)
        return oauth.ocidomain.authorize_redirect(uri)
    
    else:
        return redirect(url_for('home'))
    
@app.route('/callback')
def callback():
    token = oauth.ocidomain.authorize_access_token()
    app.logger.debug(f'Returned OAuth Token: {token}')
    session['user'] = token['userinfo']
    session['id_token'] = token['id_token']
    app.logger.debug(f'Decoded ID Token: {token["userinfo"]}')
    return redirect(url_for('home'))

# Logout behavior
@app.route('/logout')
def logout():
    if session.get('user'):
        url = f'{idm_host}/oauth2/v1/userlogout?id_token_hint={session.get("id_token")}'
        url += f'&post_logout_redirect_uri={app_host}{url_for("home")}'
        session.clear()
        return redirect(url)
    
    return redirect(url_for('home'))

# Resource deletion logic
@app.route('/delete', methods=['DELETE'])
def delete():
    # TODO
    return redirect(url_for('home'))

# Resource update logic; Will be used for updating expiry tag
@app.route('/update', methods=['PATCH'])
def update():
    # TODO
    return redirect(url_for('home'))

### Error Handlers ###

@app.errorhandler(exceptions.BadRequest)
def bad_request(e):
    return '<h1>400 Bad Request</h1><a href="/">Home</a>', 400

@app.errorhandler(exceptions.Unauthorized)
def unauthorized(e):
    return '<h1>401 Unauthorized</h1><a href="/">Home</a>', 401

@app.errorhandler(exceptions.Forbidden)
def forbidden(e):
    return '<h1>403 Forbidden</h1><a href="/">Home</a>', 403

@app.errorhandler(exceptions.NotFound)
def not_found(e):
    return '<h1>404 Not Found</h1><a href="/">Home</a>', 404

@app.errorhandler(exceptions.InternalServerError)
def server_error(e):
    return '<h1>500 Internal Server Error</h1><a href="/">Home</a>', 500
