#!/usr/bin/python3.11

from authlib.integrations.flask_client import OAuth
from cachelib import FileSystemCache
from datetime import timedelta
from flask import Flask, session, redirect, render_template, url_for
from flask_session import Session
from os import getenv
from werkzeug import exceptions

### Globals
TIMEOUT_IN_SECONDS = 900
PREFIX = 'OCIDOMAIN'
idm_host = getenv(f'{PREFIX}_IDM_ENDPOINT')
app_host = getenv(f'{PREFIX}_APP_URI')

app = Flask(__name__)
app.config['SESSION_COOKIE_NAME'] = 'omid'
app.config['SESSION_TYPE'] = 'cachelib'
app.config['SESSION_CACHELIB'] = FileSystemCache('session',
                                                 default_timeout=TIMEOUT_IN_SECONDS)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=TIMEOUT_IN_SECONDS)
Session(app)

# OIDC
oauth = OAuth(app)
oauth.register(
    'ocidomain',
    client_id=getenv(f'{PREFIX}_CLIENT_ID'),
    client_secret=getenv(f'{PREFIX}_CLIENT_SECRET'),
    server_metadata_url=f'{idm_host}/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid'})

###

@app.route('/', methods=['GET'])
def home():
    if session.get('user'):
        # TODO items logic
        items = [{'foo': 'bar',
             'boo': 'baz'}]
        return render_template('index.html',
                               name=session.get('user')['sub'],
                               items=items)
    
    return render_template('index.html')

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

@app.route('/logout')
def logout():
    if session.get('user'):
        url = f'{idm_host}/oauth2/v1/userlogout?id_token_hint={session.get("id_token")}'
        url += f'&post_logout_redirect_uri={app_host}{url_for("home")}'
        session.clear()
        return redirect(url)
    
    return redirect(url_for('home'))

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
