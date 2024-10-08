import jwt
import json
import requests
import logging

from werkzeug import exceptions

from ..utils import log_factory


class Authenticator:
    def __init__(self,
                 oidc_provider: str,
                 client_id: str,
                 client_secret:str,
                 scope: str='openid email',
                 handler=logging.StreamHandler(),
                 log_level=logging.INFO,
                 **kwargs):
        
        # Logging
        self.logger = log_factory(__name__, log_level, handler)

        self.idm_url = oidc_provider
        self.client = client_id
        self.secret = client_secret
        self.oidc_config = requests.get(
            f'{oidc_provider}/.well-known/openid-configuration').json()
        self.algos = self.oidc_config['id_token_signing_alg_values_supported']
        self.scope = scope
        self.jwks_client = jwt.PyJWKClient(self.oidc_config['jwks_uri'])
        self.logger.info('Authenticator initialized')
        self.logger.debug(f'\tIDM URL: {self.idm_url}\n'
                          f'\tClient ID: {self.client}\n'
                          f'\tOIDC Config: {json.dumps(self.oidc_config)}\n'
                          f'\tSigning Algorithms: {self.algos}\n'
                          f'\tScope: {self.scope}\n')

    # Returns a crafted redirect to send users to the OIDC provider endpoint. State
    # and nonce should be cryptographically randomized strings.
    def login_redirect_uri(self, callback: str, nonce: str, state: str) -> str:
        self.logger.debug(f'Crafting redirect URL with state {state} and nonce {nonce}')

        url = (f'{self.idm_url}/oauth2/v1/authorize'
               f'?client_id={self.client}&response_type=code'
               f'&redirect_uri={callback}'
               f'&scope={self.scope}&nonce={nonce}&state={state}')
        
        self.logger.debug(f'Redirect URL: {url}')
        return url
    
    def logout_redirect_uri(self, id_token: str, redirect_uri:str) -> str:
        url = (f'{self.idm_url}/oauth2/v1/userlogout?id_token_hint={id_token}'
               f'&post_logout_redirect_uri={redirect_uri}')
        
        self.logger.debug(f'Post Logout URL: {url}')
        
        return url
    
    # Retrieves token and returns a tuple of (JWT, Access Token, Decoded ID Token)
    def retrive_token(self, code: str, nonce: str | None) -> dict:
        r = requests.post(f'{self.idm_url}/oauth2/v1/token',
                          auth=(self.client, self.secret),
                          data={'grant_type': 'authorization_code',
                                'code': code})
        
        token = r.json() # Raw token in JSON format

        # Dict of various token types
        tokens = {
            'token': r.text, # Raw token in text format
            'access_token': token['access_token'], # Encoded Access Token
            'id_token': token['id_token'], # Encoded ID Token
            # Decoded ID Token
            'decoded_token': self.decode_jwt(token['id_token'],
                                             nonce)
        }

        self.logger.debug(f'Retrieved token {tokens}')
        
        return tokens
    
    # Decode and verify returned JWT
    def decode_jwt(self, id_token: str, nonce: str | None) -> dict:
        signing_key = self.jwks_client.get_signing_key_from_jwt(id_token)

        try:
            data = jwt.decode(
                id_token,
                key=signing_key.key,
                algorithms=self.algos,
                audience=self.client,
                issuer=self.oidc_config['issuer']
            )
        except jwt.DecodeError as e:
            self.logger.error(f'Failed to decode token: {e}')
            raise exceptions.BadRequest
        except Exception as e:
            self.logger.info(f'Token failed inspection with exception {e}: {id_token}')
            raise exceptions.BadRequest
        
        if nonce:
            if nonce != data['nonce']:
                raise exceptions.BadRequest
        
        self.logger.debug(f'Decoded ID Token: {data}')
        return data
    
    # Recieves an access token and returns info about the user from the IdP
    def retrieve_userinfo(self, at: str):
        r = requests.get(f'{self.idm_url}/oauth2/v1/userinfo', headers={
            'Authorization': f'Bearer {at}',
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
        })

        self.logger.debug(f'Returned user info: {r.json()}')
        return r.json()