import base64
import json
import logging
import binascii

import requests

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from collections.abc import Callable
from oci.auth.signers import get_resource_principals_signer
from oci.signer import Signer
from oci.exceptions import ServiceError
from oci.secrets import SecretsClient

class Authenticator:
    """Authenticator handles all authentication and token handling tasks for the
       application.
    """

    def __init__(self, log_callable: Callable, url: str, secret: str, 
                 passwd: str=None, signer: Signer=get_resource_principals_signer()):
        self.log: logging.Logger = log_callable(__name__)

        self.idcs_url: str = url
        self.password: str | None = passwd

        # Get Client ID & Secret
        self.client_id, self.client_secret = self._get_client_id_secret(signer,
                                                                        secret)
        
    # authenticate collects key and token to return as dict
    def authenticate(self, access_tok: str) -> dict:
        token, key = self.get_upst(access_tok)

        return {'key': key, 'token': token}

    # get_upst takes an access token and returns a UPST and private key
    def get_upst(self, access_tok: str) -> tuple[str, str]:
        
        private_key, public_key = self.generate_keys()

        # Get UPST
        data = {
            'grant_type': 'urn:ietf:params:oauth:grant-type:token-exchange',
            'requested_token_type': 'urn:oci:token-type:oci-upst',
            'subject_token_type': 'jwt',
            # Strip first and last 26 characters to remove headers
            'public_key': self.generate_public_pem(public_key)[26:-26],
            'subject_token': access_tok
        }

        r = requests.post(
            f'{self.idcs_url}/oauth2/v1/token',
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            auth=(self.client_id,
                self.client_secret))
        self.log.debug(f'UPST endpoint response: {r.status_code}')
        
        token = r.json()['token']

        # 1. JWT body selected by split
        # 2. Extra padding (==) added for decoding; Decoder will remove as needed
        # 3. Decode into bytes
        # 4. Load into dict
        # 5. Select 'sub' claim
        user = json.loads(base64.b64decode(token.split('.')[1] + '=='))['sub']
        self.log.info(json.dumps({
            'message': f'retrieved token for user {user}'
        }))

        return token, self.generate_private_pem(private_key, self.password).decode()
    
    # Return 'sub' claim from JWT to identify subject
    def get_claim_sub(self, token: str) -> str:
        return self.decode_jwt(token)['claims']['sub']
    
    # decode_jwt turns a token in JWT format and decodes it. Does no validation.
    def decode_jwt(self, token: str) -> dict:
        # Assumes JWT with headers.claims format
        decoded = {}
        sections = token.split('.')
        # Add extra '=' to prevent padding errors
        decoded['header'] = json.loads(base64.b64decode(f'{sections[0]}=='))
        decoded['claims'] = json.loads(base64.b64decode(f'{sections[1]}=='))
        
        # Get signature if possible
        try:
            decoded['signature'] = base64.b64decode(f'{sections[2]}==')
        except IndexError:
            self.log.warning('invalid signature in JWT')
        except binascii.Error:
            self.log.warning(f'invalid base64 encoding: {sections[2]}')
        
        return decoded

    def generate_keys(self) -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
        self.log.debug('Generating RSA key pair')

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )

        public_key = private_key.public_key()

        return private_key, public_key

    def generate_public_pem(self, public_key: rsa.RSAPublicKey) -> bytes:
        self.log.debug('Generating public key bytes')
        return public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def generate_private_pem(self, private_key: rsa.RSAPrivateKey,
                            password: str | None) -> bytes:
        self.log.debug(f'Generating private key bytes with password {password}')
        
        # Apply encryption to private key using password
        if password:
            return private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.BestAvailableEncryption(
                    password.encode())
            )

        # No encryption
        return private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
    
    # Load private pem serializes a private key
    def load_private_pem(self, key: str) -> rsa.RSAPrivateKey:
        key = key.encode()

        # Convert password to bytes if present
        password = self.password.encode() if self.password else None

        self.log.debug(
            f'Loading private key from data {key} and password {self.password}')

        return serialization.load_pem_private_key(key, password)
    
    def _get_client_id_secret(self, signer, secret) -> tuple[str, str]:
        cfg = {'region': signer.region, 'tenancy': signer.tenancy_id}
        client = SecretsClient(cfg, signer=signer)

        try:
            r = client.get_secret_bundle(secret)
        except ServiceError as e:
            self.log.error(f'service error raised: {e}')
            raise ConfigError(str(e))
        
        content = base64.b64decode(r.data.secret_bundle_content.content).decode()
        id, secret = content.split(':')

        return id, secret
    

class ConfigError(Exception):
    def __init__(self, *args):
        super().__init__(*args)


class AuthenticationError(Exception):
    def __init__(self, message='exception occurred during user authentication',
                 code: int|None=None, data: dict|None=None):
        self.message = message
        self.code = code
        self.data = data
        super().__init__(self.message)

    def __str__(self):
        return f'{self.message} -- code {self.code}'