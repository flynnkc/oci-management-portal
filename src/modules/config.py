#!/usr/bin/python3.11

import logging

from os import getenv
from types import MethodType
from os.path import expanduser

from oci.config import DEFAULT_LOCATION, DEFAULT_PROFILE
from oci import identity, Response
from .signer import create_signer


class Tag:
    def __init__(self, namespace: str, key: str) -> None:
        self.namespace: str = namespace
        self.key: str = key

    def __repr__(self) -> str:
        return f'Namespace: {self.namespace}\tKey: {self.key}'


class ConfigurationException(Exception):
    pass


class Configuration:
    """
    Central configuration loader. Supports using environment variables to configure
    behavior of application.
    """

    def __init__(self, prefix="OCI_MGMT_DASH", **kwargs) -> None:
        # Store prefix for validation/help messages
        self.prefix = prefix

        # Variables with defaults
        self._uri: str = 'http://localhost:5000'
        self._behind_proxy: bool = False
        self._auth_type: str = 'profile'
        self._config_file: str = DEFAULT_LOCATION
        self._profile: str = DEFAULT_PROFILE
        self._log_level:str = 'info'
        self._log_format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        self._session_backend: str = 'filesystem'
        self._session_redis_url: str = ''
        self._session_redis_username: str = ''
        self._session_redis_password: str = ''
        self._session_key_prefix: str = 'omid:'
        self._user_scoped_oci_calls: bool = True
        self._token_exchange_enabled: bool = True
        self._token_exchange_scope: str = ''
        self._token_exchange_audience: str = ''
        self._token_exchange_requested_token_type: str = 'urn:ietf:params:oauth:token-type:access_token'
        self._token_exchange_subject_token_type: str = 'urn:ietf:params:oauth:token-type:access_token'
        self._token_exchange_expiry_skew_seconds: int = 60

        # Required variables
        self._tag_namespace: str
        self._tag_key: str
        self._filter_key: str
        self._cleanup_compartment: str
        self._idm_ocid: str
        self._idm_endpoint: str
        self._idm_client_id: str
        self._idm_client_secret: str

        # Optional variables
        self._filter_namespace: str

        # Load from environment
        self.parse_env(prefix)

        # Derive defaults without writing None
        if not self.get_filter().namespace and self.get_mgmt_tag().namespace:
            self.set_filter(self.get_mgmt_tag().namespace, None)

        # Initialize logging handler
        self._handler = self._create_handler()

        # Validate required settings
        self.validate()

    def __repr__(self) -> str:
        app = {'uri': self.get_uri(),
               'cleanup_compartment': self.get_cleanup_compartment(),
               'tags': self.get_mgmt_tag(),
               'filter': self.get_filter()}
        auth = {'auth_type': self.get_auth_type(),
                'config_file': self.get_config_file(),
                'profile': self.get_profile()}
        idm = {'domain_endpoint': self.get_idm_endpoint(),
               'client_id': self.get_idm_client_id(),
               'client_secret': self.get_idm_client_secret(redacted=True)}
        logs = {'log_level': self.get_log_level(),
                'log_fmt': self.get_log_format()}
        session = {
            'backend': self.get_session_backend(),
            'redis_url': self.get_session_redis_url(redacted=True),
            'redis_username': self.get_session_redis_username(),
            'redis_password': self.get_session_redis_password(redacted=True),
            'key_prefix': self.get_session_key_prefix(),
            'user_scoped_oci_calls': self.get_user_scoped_oci_calls(),
            'token_exchange_enabled': self.get_token_exchange_enabled(),
            'token_exchange_scope': self.get_token_exchange_scope(),
            'token_exchange_audience': self.get_token_exchange_audience(),
            'token_exchange_requested_token_type': self.get_token_exchange_requested_token_type(),
            'token_exchange_subject_token_type': self.get_token_exchange_subject_token_type(),
            'token_exchange_expiry_skew_seconds': self.get_token_exchange_expiry_skew_seconds(),
        }
        return (
            "Configuration:\n"
            f"\tApp Settings - {app}\n"
            f"\tAuthentication Settings - {auth}\n"
            f"\tIdentity Management Settings - {idm}\n"
            f"\tLogging Settings - {logs}\n"
            f"\tSession Settings - {session}"
        )
    
    def validate(self) -> None:
        """Validate required configuration values and raise ConfigurationException if missing."""
        required = {
            "app.cleanupcompartment": (self._cleanup_compartment, f"{self.prefix}_CLEANUP_CMP"),
            "app.tagnamespace": (self._tag_namespace, f"{self.prefix}_TAG_NAMESPACE"),
            "app.tagkey": (self._tag_key, f"{self.prefix}_TAG_KEY"),
            "app.filterkey": (self._filter_key, f"{self.prefix}_FILTER_KEY"),
            "idm.endpoint": (self._idm_endpoint, f"{self.prefix}_IDM_ENDPOINT"),
            "idm.clientid": (self._idm_client_id, f"{self.prefix}_CLIENT_ID"),
            "idm.clientsecret": (self._idm_client_secret, f"{self.prefix}_CLIENT_SECRET"),
        }
        missing = [f"{k} (env: {env})" for k, (v, env) in required.items() if not v]
        if missing:
            raise ConfigurationException(
                "Missing required configuration values:\n" + "\n".join(f" - {m}" for m in missing)
            )

        if self.get_session_backend() in ('redis', 'valkey') and not self.get_session_redis_url():
            raise ConfigurationException(
                f"Missing required configuration value for shared session cache:\n"
                f" - session.redis_url (env: {self.prefix}_SESSION_REDIS_URL)"
            )

    def parse_env(self, PREFIX: str):
        # Read values from environment variables; only set when non-empty
        control: dict[str, MethodType] = {
            f'{PREFIX}_IDM_ENDPOINT': self.set_idm_endpoint,
            f'{PREFIX}_CLIENT_ID': self.set_idm_client_id,
            f'{PREFIX}_CLIENT_SECRET': self.set_idm_client_secret,
            f'{PREFIX}_CLEANUP_CMP': self.set_cleanup_compartment,
            f'{PREFIX}_TAG_NAMESPACE': self.set_mgmt_tag_namespace,
            f'{PREFIX}_TAG_KEY': self.set_mgmt_tag_key,
            f'{PREFIX}_FILTER_NAMESPACE': self.set_filter_namespace,
            f'{PREFIX}_FILTER_KEY': self.set_filter_key,
            f'{PREFIX}_APP_URI': self.set_uri,
            f'{PREFIX}_AUTH_TYPE': self.set_auth_type,
            f'{PREFIX}_PROFILE': self.set_profile,
            f'{PREFIX}_CONFIG_FILE': self.set_config_file,
            f'{PREFIX}_LOG_LEVEL': self.set_log_level,
            f'{PREFIX}_LOG_FORMAT': self.set_log_format,
            f'{PREFIX}_PROXY': self.set_proxy,
            f'{PREFIX}_SESSION_BACKEND': self.set_session_backend,
            f'{PREFIX}_SESSION_REDIS_URL': self.set_session_redis_url,
            f'{PREFIX}_SESSION_REDIS_USERNAME': self.set_session_redis_username,
            f'{PREFIX}_SESSION_REDIS_PASSWORD': self.set_session_redis_password,
            f'{PREFIX}_SESSION_KEY_PREFIX': self.set_session_key_prefix,
            f'{PREFIX}_USER_SCOPED_OCI_CALLS': self.set_user_scoped_oci_calls,
            f'{PREFIX}_TOKEN_EXCHANGE_ENABLED': self.set_token_exchange_enabled,
            f'{PREFIX}_TOKEN_EXCHANGE_SCOPE': self.set_token_exchange_scope,
            f'{PREFIX}_TOKEN_EXCHANGE_AUDIENCE': self.set_token_exchange_audience,
            f'{PREFIX}_TOKEN_EXCHANGE_REQUESTED_TOKEN_TYPE': self.set_token_exchange_requested_token_type,
            f'{PREFIX}_TOKEN_EXCHANGE_SUBJECT_TOKEN_TYPE': self.set_token_exchange_subject_token_type,
            f'{PREFIX}_TOKEN_EXCHANGE_EXPIRY_SKEW_SECONDS': self.set_token_exchange_expiry_skew_seconds,
        }

        for key, fn in control.items():
            val = getenv(key)
            if val:
                fn(val)

    
    #Enable  Logging
    
    def get_log_level(self) -> str:
        # Return upper-case textual level for readability
        return self._log_level.upper()

    def set_log_level(self, level: str | int):
        # Normalize and update handler if present
        if isinstance(level, int):
            # Map back to name for storage
            name = logging.getLevelName(level)
            self._log_level = str(name).lower()
            if hasattr(self, "handler") and self._handler:
                self._handler.setLevel(level)
        else:
            name = str(level).lower()
            self._log_level = name
            if hasattr(self, "handler") and self._handler:
                lvl = getattr(logging, name.upper(), logging.INFO)
                self._handler.setLevel(lvl)

    def get_log_handler(self) -> logging.Handler:
        return self._handler

    def set_log_handler(self, handler: logging.Handler):
        self._handler = handler

    def get_log_format(self) -> str:
        return self._log_format
    
    def set_log_format(self, log_format: str):
        self._log_format = log_format

    # Properties and setters for common fields (Pythonic API)
    def get_uri(self) -> str:
        return self._uri

    def set_uri(self, uri: str):
        self._uri = uri

    def get_proxy(self) -> bool:
        return self._behind_proxy

    def set_proxy(self, value: str | bool):
        if isinstance(value, bool):
            self._behind_proxy = value
            return

        truthy = {'1', 'true', 't', 'yes', 'y', 'on'}
        self._behind_proxy = str(value).strip().lower() in truthy

    @staticmethod
    def _as_bool(value: str | bool) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {'1', 'true', 't', 'yes', 'y', 'on'}

    def get_cleanup_compartment(self) -> str:
        return self._cleanup_compartment
    
    def set_cleanup_compartment(self, cmp: str):
        self._cleanup_compartment = cmp

    def get_auth_type(self) -> str:
        return self._auth_type.lower()

    def set_auth_type(self, authtype: str):
        self._auth_type = authtype

    def get_profile(self) -> str:
        if self.get_auth_type() != 'profile':
            return 'Not applicable'
        return self._profile

    def set_profile(self, profile: str):
        self._profile = profile

    def get_config_file(self) -> str:
        if self.get_auth_type() != 'profile':
            return 'Not applicable'
        return self._config_file

    def set_config_file(self, path: str):
        val = expanduser(path)
        self._config_file = val

    def get_mgmt_tag(self) -> Tag:
        return Tag(self._tag_namespace, self._tag_key)

    def set_mgmt_tag(self, tagnamespace: str | None, tagkey: str | None):
        if tagnamespace: self._tag_namespace = tagnamespace
        if tagkey: self._tag_key = tagkey

    def set_mgmt_tag_namespace(self, namespace: str):
        self._tag_namespace = namespace

    def set_mgmt_tag_key(self, key: str):
        self._tag_key = key

    # Prefer explicitly configured filter namespace; fall back to mgmt tag namespace
    def get_filter(self) -> Tag:
        return Tag(getattr(self, '_filter_namespace', self.get_mgmt_tag().namespace),
                   self._filter_key)

    def set_filter(self, filternamespace: str | None, filterkey: str | None):
        if filternamespace: self._filter_namespace = filternamespace
        if filterkey: self._filter_key = filterkey

    def set_filter_namespace(self, namespace: str):
        self._filter_namespace = namespace

    def set_filter_key(self, key: str):
        self._filter_key = key
    
    def get_idm_endpoint(self) -> str:
        if not getattr(self, '_idm_endpoint', ''):
            endpoint = self._retrieve_idm_endpoint()
            self.set_idm_endpoint(endpoint)

        return self._idm_endpoint
    
    def set_idm_endpoint(self, endpoint: str):
        self._idm_endpoint = endpoint

    def get_idm_ocid(self) -> str:
        return self._idm_ocid
    
    def set_idm_ocid(self, ocid: str):
        self._idm_ocid = ocid

    def get_idm_client_id(self) -> str:
        return self._idm_client_id
    
    def set_idm_client_id(self, id: str):
        self._idm_client_id = id

    def get_idm_client_secret(self, redacted: bool=False) -> str:
        if redacted:
            return '**** REDACTED ****'
        else:
            return self._idm_client_secret
        
    def set_idm_client_secret(self, secret: str):
        self._idm_client_secret = secret

    def _create_handler(self) -> logging.Handler:
        handler = logging.StreamHandler()
        lvl = getattr(logging, self.get_log_level(), logging.INFO)
        handler.setLevel(lvl)
        handler.setFormatter(logging.Formatter(self.get_log_format()))
        return handler
    
    def _retrieve_idm_endpoint(self) -> str:
        cfg, signer = create_signer(authentication_type=self.get_auth_type(),
                               profile=self.get_profile(),
                               location=self.get_config_file())
        client = identity.IdentityClient(cfg, signer=signer)

        response: Response = client.get_domain(self.get_idm_ocid())
        return response.data.url

    def get_session_backend(self) -> str:
        return self._session_backend.lower()

    def set_session_backend(self, backend: str):
        normalized = str(backend).strip().lower()
        if normalized not in {'filesystem', 'redis', 'valkey'}:
            raise ConfigurationException(
                f"Invalid session backend '{backend}'. Supported values: filesystem, redis, valkey"
            )
        self._session_backend = normalized

    def get_session_redis_url(self, redacted: bool = False) -> str:
        if not self._session_redis_url:
            return ''
        if redacted:
            return '**** REDACTED ****'
        return self._session_redis_url

    def set_session_redis_url(self, redis_url: str):
        self._session_redis_url = redis_url

    def get_session_redis_username(self) -> str:
        return self._session_redis_username

    def set_session_redis_username(self, username: str):
        self._session_redis_username = username

    def get_session_redis_password(self, redacted: bool = False) -> str:
        if not self._session_redis_password:
            return ''
        if redacted:
            return '**** REDACTED ****'
        return self._session_redis_password

    def set_session_redis_password(self, password: str):
        self._session_redis_password = password

    def get_session_key_prefix(self) -> str:
        return self._session_key_prefix

    def set_session_key_prefix(self, key_prefix: str):
        self._session_key_prefix = key_prefix

    def get_user_scoped_oci_calls(self) -> bool:
        return self._user_scoped_oci_calls

    def set_user_scoped_oci_calls(self, enabled: str | bool):
        self._user_scoped_oci_calls = self._as_bool(enabled)

    def get_token_exchange_enabled(self) -> bool:
        return self._token_exchange_enabled

    def set_token_exchange_enabled(self, enabled: str | bool):
        self._token_exchange_enabled = self._as_bool(enabled)

    def get_token_exchange_scope(self) -> str:
        return self._token_exchange_scope

    def set_token_exchange_scope(self, scope: str):
        self._token_exchange_scope = scope

    def get_token_exchange_audience(self) -> str:
        return self._token_exchange_audience

    def set_token_exchange_audience(self, audience: str):
        self._token_exchange_audience = audience

    def get_token_exchange_requested_token_type(self) -> str:
        return self._token_exchange_requested_token_type

    def set_token_exchange_requested_token_type(self, token_type: str):
        self._token_exchange_requested_token_type = token_type

    def get_token_exchange_subject_token_type(self) -> str:
        return self._token_exchange_subject_token_type

    def set_token_exchange_subject_token_type(self, token_type: str):
        self._token_exchange_subject_token_type = token_type

    def get_token_exchange_expiry_skew_seconds(self) -> int:
        return self._token_exchange_expiry_skew_seconds

    def set_token_exchange_expiry_skew_seconds(self, seconds: str | int):
        try:
            value = int(seconds)
        except (TypeError, ValueError):
            value = 60
        self._token_exchange_expiry_skew_seconds = max(0, value)
