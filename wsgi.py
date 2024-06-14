import requests
import secrets
import jwt

from datetime import timedelta
from os import getenv
from cachelib import FileSystemCache
from flask import Flask, request, session, redirect, url_for
from flask_session import Session
from werkzeug import exceptions

### Globals
TIMEOUT_IN_SECONDS = 900

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'cachelib'
app.config['SESSION_CACHELIB'] = FileSystemCache('session',
                                                 default_timeout=TIMEOUT_IN_SECONDS)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=TIMEOUT_IN_SECONDS)
Session(app)

# Environment variable names
client_id = getenv('CLIENT_ID')
host = getenv('IDM_ENDPOINT')
client_secret = 'CLIENT_SECRET'

# OIDC
oidc_config = requests.get(f'{host}/.well-known/openid-configuration').json()
signing_alg = oidc_config['id_token_signing_alg_values_supported']
jwks_client = jwt.PyJWKClient(oidc_config['jwks_uri'])

###

@app.route('/', methods=['GET'])
def home():
    if not session.get('username'):
        resp = '<h1>Welcome</h1>'
        resp += f'<h2>{request.base_url}</h2>'
        resp += f'<a href="{url_for("sign_in")}">Sign In</a>'
        return resp
    else:
        resp = f'<h1>Welcome, {session["display_name"]}</h1>'
        resp += f'<h2>{request.base_url}</h2>'
        resp += f'<a href="{url_for("logout")}">Log out</a>'
        return resp

@app.route('/signin', methods=['GET'])
def sign_in():
    if not session.get('username'):
        nonce = secrets.token_urlsafe()
        state = secrets.token_urlsafe()
        app.logger.debug(f'State: {state}\n\tNonce: {nonce}')

        session['state'] = state
        session['nonce'] = nonce
        app.logger.debug(f'Session: {session.items()}')

        url = f'{host}/oauth2/v1/authorize'
        url += f'?client_id={client_id}&response_type=code'
        url += f'&redirect_uri=http://localhost:5000{url_for("callback")}'
        url += f'&scope=openid&nonce={nonce}'
        url += f'&state={state}'
        app.logger.debug(f'Signin redirect URL: {url}')
        return redirect(url)
    
    else:
        return f'<h1>Hello{session.get("name")}, you are already signed in</h1><a href="{url_for("logout")}">Log out?</a>'
    
@app.route('/callback', methods=['GET'])
def callback():
    if request.args.get('state') != session.pop('state'):
        raise exceptions.BadRequest
    
    code = request.args.get('code')
    if code:
        r = requests.post(f'{host}/oauth2/v1/token',
                      auth=(client_id, getenv(client_secret)),
                      data={'grant_type': 'authorization_code',
                            'code': code})
        tok = r.json()['id_token'] # JWT

        signing_key = jwks_client.get_signing_key_from_jwt(tok)

        try:
            data = jwt.decode(tok,
                key=signing_key.key,
                algorithms=signing_alg,
                audience=client_id)
        except Exception as e:
            app.logger.debug(f"Error decoding JWT: {e}")
            app.logger.debug(f'JWT Token: {tok}')
        
        app.logger.debug(f'JWT Decoded: {data}')

        app.logger.debug(f'Nonce: Session - {session.get("nonce")}\tToken - {data["nonce"]}')
        if session.pop('nonce') != data['nonce']:
            raise exceptions.BadRequest

        session['username'] = f'{data["domain"]}/{data["sub"]}'
        session['display_name'] = data['user_displayname']
        
        return redirect(url_for('home'))

    raise exceptions.Unauthorized

@app.route('/logout')
def logout():
    session.clear()
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
