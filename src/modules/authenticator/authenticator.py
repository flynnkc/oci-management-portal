import jwt
import json
import requests
import logging
from time import time
from typing import Any

from werkzeug import exceptions

from ..utils import log_factory


class Authenticator:
    """OIDC/OAuth helper for login, token handling, and user-context derivation.

    Responsibilities:
    - Build authorization/logout redirects
    - Exchange authorization codes and tokens
    - Validate ID tokens and fallback to introspection when needed
    - Normalize user identity context for session storage
    """

    # OAuth2 token exchange grant for UPST/access-token exchange flows.
    UPST_GRANT_TYPE: str = 'urn:ietf:params:oauth:grant-type:token-exchange'

    def __init__(self,
                 oidc_provider: str,
                 client_id: str,
                 client_secret:str,
                 scope: str='openid email',
                 handler: logging.Handler=logging.StreamHandler(),
                 log_level: int | str=logging.INFO,
                 **kwargs):
        """Initialize authenticator and cache OIDC discovery metadata."""
        
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

    def login_redirect_uri(self, callback: str, nonce: str, state: str) -> str:
        """Build authorization redirect URI.

        `state` and `nonce` should be cryptographically random values generated
        by the caller and persisted in session for callback validation.
        """
        self.logger.debug(f'Crafting redirect URL with state {state} and nonce {nonce}')

        url = (f'{self.idm_url}/oauth2/v1/authorize'
               f'?client_id={self.client}&response_type=code'
               f'&redirect_uri={callback}'
               f'&scope={self.scope}&nonce={nonce}&state={state}')
        
        self.logger.debug(f'Redirect URL: {url}')
        return url
    
    def logout_redirect_uri(self, id_token: str, redirect_uri:str) -> str:
        """Build provider logout redirect URI using id_token_hint."""
        url = (f'{self.idm_url}/oauth2/v1/userlogout?id_token_hint={id_token}'
               f'&post_logout_redirect_uri={redirect_uri}')
        
        self.logger.debug(f'Post Logout URL: {url}')
        
        return url
    
    def retrieve_token(self, code: str, nonce: str | None) -> dict[str, Any]:
        """Exchange authorization code and return callback-relevant token data."""
        r = requests.post(f'{self.idm_url}/oauth2/v1/token',
                          auth=(self.client, self.secret),
                          data={'grant_type': 'authorization_code',
                                'code': code})

        if r.status_code >= 400:
            self.logger.warning('Token exchange failed status=%s body=%s', r.status_code, r.text)
            raise exceptions.Unauthorized

        token = r.json()
        if not token.get('id_token'):
            self.logger.warning('Token exchange response missing required id_token field')
            raise exceptions.BadRequest

        # Validate ID token immediately and return only what callback needs.
        id_claims = self.decode_jwt(token['id_token'], nonce)

        return {
            'id_claims': id_claims,
            # Access token is optional in callback flow; only used for
            # introspection fallback when ID token claims are insufficient.
            'access_token': token.get('access_token'),
            'refresh_token': token.get('refresh_token'),
            'expires_in': token.get('expires_in'),
        }

    def exchange_token(
        self,
        subject_token: str,
        scope: str | None = None,
        audience: str | None = None,
        requested_token_type: str = 'urn:ietf:params:oauth:token-type:access_token',
        subject_token_type: str = 'urn:ietf:params:oauth:token-type:access_token'
    ) -> dict[str, Any]:
        """Perform OAuth2 token exchange and return token metadata.

        The method is intentionally generic so callers can request OCI-specific
        token types (e.g., UPST) by passing a different requested_token_type.
        """
        endpoint = self.oidc_config.get('token_endpoint', f'{self.idm_url}/oauth2/v1/token')
        data = {
            'grant_type': Authenticator.UPST_GRANT_TYPE,
            'subject_token': subject_token,
            'subject_token_type': subject_token_type,
            'requested_token_type': requested_token_type,
        }
        if scope:
            data['scope'] = scope
        if audience:
            data['audience'] = audience

        r = requests.post(endpoint, auth=(self.client, self.secret), data=data)
        if r.status_code >= 400:
            self.logger.warning('Token exchange failed status=%s', r.status_code)
            raise exceptions.Unauthorized

        token = r.json()
        access_token = token.get('access_token')
        if not access_token:
            self.logger.warning('Token exchange response missing required access_token field')
            raise exceptions.BadRequest

        expires_in = token.get('expires_in') or 0
        try:
            expires_in_seconds = int(expires_in)
        except (TypeError, ValueError):
            expires_in_seconds = 0

        return {
            'access_token': access_token,
            'issued_at': int(time()),
            'expires_in': expires_in_seconds,
            'expires_at': int(time()) + expires_in_seconds if expires_in_seconds > 0 else 0,
            'token_type': token.get('token_type'),
            'scope': token.get('scope'),
        }

    def introspect_token(self, access_token: str) -> dict[str, Any]:
        """Introspect access token and return active payload."""
        endpoint = self.oidc_config.get(
            'introspection_endpoint',
            f'{self.idm_url}/oauth2/v1/introspect',
        )
        r = requests.post(
            endpoint,
            auth=(self.client, self.secret),
            data={
                'token': access_token,
                'token_type_hint': 'access_token',
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )

        if r.status_code >= 400:
            self.logger.warning('Token introspection failed status=%s body=%s', r.status_code, r.text)
            raise exceptions.Unauthorized

        payload = r.json()
        if not payload.get('active'):
            self.logger.info('Token introspection indicates inactive token')
            raise exceptions.Unauthorized

        return payload

    def build_user_context(
        self,
        id_claims: dict[str, Any],
        introspection: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create normalized user context from ID claims and optional introspection."""
        introspection = introspection or {}
        email = (
            introspection.get('email')
            or introspection.get('username')
            or id_claims.get('email')
            or id_claims.get('preferred_username')
            or id_claims.get('sub')
        )
        if not email:
            self.logger.warning('Unable to derive user identity from ID token/introspection claims')
            raise exceptions.BadRequest

        domain = introspection.get('domain') or id_claims.get('domain')
        if not domain and isinstance(email, str) and '@' in email:
            domain = email.split('@', 1)[1]

        user = f'{domain}/{email}' if domain else str(email)
        return {
            'user': user,
            'email': email,
            'domain': domain,
            'sub': id_claims.get('sub') or introspection.get('sub'),
        }
    
    def decode_jwt(
        self,
        id_token: str,
        nonce: str | None,
        inspect: bool = True,
    ) -> dict[str, Any]:
        """Decode and verify ID token; optionally enforce nonce match."""
        signing_key = self.jwks_client.get_signing_key_from_jwt(id_token)

        try:
            data = jwt.decode(
                id_token,
                key=signing_key.key,
                algorithms=self.algos,
                audience=self.client,
                issuer=self.oidc_config['issuer'],
                options={'verify_signature': inspect}
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
    
    def retrieve_userinfo(self, at: str) -> dict[str, Any]:
        """Call userinfo endpoint and return raw claims payload."""
        r = requests.get(f'{self.idm_url}/oauth2/v1/userinfo', headers={
            'Authorization': f'Bearer {at}',
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
        })

        self.logger.debug(f'Returned user info: {r.json()}')
        return r.json()