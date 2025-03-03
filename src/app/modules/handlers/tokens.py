import json

from base64 import b64decode

import requests

# authenticate is responsible for making requests to the token exchange endpoint
def authenticate(hostname: str, access_token: str) -> dict:
    response = requests.post(f'https://{hostname}/auth', json={'at': access_token})
    if response.status_code != 200:
        raise AuthenticationError(
            message='non-200 response from token endpoint',
            code=response.status_code)

    data = response.json()
    token = data.get('token')
    key = data.get('private_key')

    if not token or not key:
        raise AuthenticationError(message='token or key not found',
                                  code=response.status_code,
                                  data=data)
    
    return {'key': key, 'token': token}

# decode_jwt turns a token in JWT format and decodes it. Does no validation.
def decode_jwt(token: str) -> dict:
    # Assumes JWT with headers.claims format
    decoded = {}
    sections = token.split('.')
    # Add extra == to prevent padding errors
    decoded['header'] = json.loads(b64decode(f'{sections[0]}=='))
    decoded['claims'] = json.loads(b64decode(f'{sections[1]}=='))
    try:
        decoded['signature'] = b64decode(f'{sections[2]}==')
    except IndexError:
        pass
    
    return decoded

def get_claim_sub(token: str) -> str:
    return decode_jwt(token)['claims']['sub']


class AuthenticationError(Exception):
    def __init__(self, message='exception occurred during user authentication',
                 code: int|None=None, data: dict|None=None):
        self.message = message
        self.code = code
        self.data = data
        super().__init__(self.message)

    def __str__(self):
        return f'{self.message} -- code {self.code}'
