import base64
import json
import requests

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from oci.auth.signers import SecurityTokenSigner

from ...utils import log_factory

log = log_factory(__name__)

def get_security_token_signer(idcs_url: str, access_tok: str, client_id: str,
                              client_secret: str) -> SecurityTokenSigner:

    token, private_key = get_upst(idcs_url, access_tok , client_id, client_secret)

    return make_security_token_signer(token, private_key)

# Get UPST returns both the token as well as the private key used to create it.
def get_upst(idcs_url: str, access_tok: str, client_id: str,
             client_secret:str) -> tuple[str, bytes]:
    
    private_key, public_key = generate_keys()

    # Get UPST
    data = {
        'grant_type': 'urn:ietf:params:oauth:grant-type:token-exchange',
        'requested_token_type': 'urn:oci:token-type:oci-upst',
        'subject_token_type': 'jwt',
        'public_key': generate_public_pem(public_key)[26:-26], # Remove headers
        'subject_token': access_tok
    }

    r = requests.post(
        f'{idcs_url}/oauth2/v1/token',
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        auth=(client_id,
            client_secret))
    log.debug(f'UPST endpoint response: {r}')
    
    token = r.json()['token']

    # 1. JWT body selected by split
    # 2. Extra padding (==) added for decoding; Decoder will remove as needed
    # 3. Decode into bytes
    # 4. Load into dict
    # 5. Select 'sub' claim
    user = json.loads(base64.b64decode(token.split('.')[1] + '=='))['sub']
    log.info(json.dumps({
        'message': f'retrived token for user {user}'
    }))

    return token, generate_private_pem(private_key)

def make_security_token_signer(token: str, private_key: bytes) -> SecurityTokenSigner:
    return SecurityTokenSigner(token, private_key)

def generate_keys() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

    public_key = private_key.public_key()

    return private_key, public_key

def generate_public_pem(public_key: rsa.RSAPublicKey) -> bytes:
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

def generate_private_pem(private_key: rsa.RSAPrivateKey) -> bytes:
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

def load_private_key(key_data: bytes) -> rsa.RSAPrivateKey:
    return serialization.load_pem_private_key(key_data, None)