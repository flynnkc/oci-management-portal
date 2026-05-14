from __future__ import annotations

from hashlib import sha256
from threading import Lock
from time import time
from typing import Any

from flask import Flask, g, session
from werkzeug import exceptions

from ..config import Configuration
from ..signer import create_signer, create_user_token_exchange_signer
from ..authenticator import Authenticator
from ..search import Search, ExpiryFilter, QueryTags
from ..delete import Deleter
from ..delete.extend import Extender
from ..request_chaser import WorkRequestChaser
from ..cost.cost_service import CostService


class ServiceContext:
    app: Flask
    config: Configuration
    cfg: dict[str, Any]
    signer: Any
    search: Search
    deleter: Deleter
    extender: Extender
    cost_service: CostService
    request_chaser: WorkRequestChaser
    oauth: Authenticator
    delete_supported_norm: set[str]
    extend_supported_norm: set[str]
    _user_signer_cache: dict[str, tuple[Any, int]]
    _user_signer_cache_lock: Lock

    def __init__(
        self,
        app: Flask,
        config: Configuration,
        cfg: dict[str, Any],
        signer: Any,
        search: Search,
        deleter: Deleter,
        extender: Extender,
        cost_service: CostService,
        request_chaser: WorkRequestChaser,
        oauth: Authenticator,
        delete_supported_norm: set[str],
        extend_supported_norm: set[str],
    ) -> None:
        self.app = app
        self.config = config
        self.cfg = cfg
        self.signer = signer
        self.search = search
        self.deleter = deleter
        self.extender = extender
        self.cost_service = cost_service
        self.request_chaser = request_chaser
        self.oauth = oauth
        self.delete_supported_norm = delete_supported_norm
        self.extend_supported_norm = extend_supported_norm

        # Process-local signer cache keyed by subject token hash.
        # Values are (signer, expires_at_epoch_seconds).
        self._user_signer_cache = {}
        self._user_signer_cache_lock = Lock()

    def _subject_token_hash(self, subject_token: str) -> str:
        return sha256(subject_token.encode('utf-8')).hexdigest()

    def _prune_local_signer_cache(self, now_epoch: int):
        with self._user_signer_cache_lock:
            stale = [k for k, (_, exp) in self._user_signer_cache.items() if exp <= now_epoch]
            for key in stale:
                self._user_signer_cache.pop(key, None)

    def _current_subject_token_details(self, require_fresh: bool = True) -> tuple[str, int]:
        """Return current subject token and its absolute expiry epoch seconds.

        If expiry metadata is missing, treat as immediately expiring for cache/TTL
        purposes while still allowing request flow when require_fresh=False.
        """
        oauth_tokens = session.get('oauth_tokens') or {}
        subject_token = oauth_tokens.get('access_token')
        if not subject_token:
            self.app.logger.warning('missing oauth access token in server session during OCI token exchange')
            raise exceptions.ServiceUnavailable

        issued_at = int(oauth_tokens.get('issued_at') or 0)
        expires_in = int(oauth_tokens.get('expires_in') or 0)
        skew = self.config.get_token_exchange_expiry_skew_seconds()
        expires_at = (issued_at + expires_in) if (issued_at and expires_in) else int(time())

        if require_fresh and issued_at and expires_in and (expires_at - skew) <= int(time()):
            self.app.logger.warning('oauth access token expired for current session during OCI token exchange')
            raise exceptions.ServiceUnavailable

        return str(subject_token), int(expires_at)

    # Returns the access_token from cache for the given user
    def _current_subject_token(self) -> str:
        subject_token, _ = self._current_subject_token_details(require_fresh=True)
        return subject_token

    def clear_user_token_exchange_cache(self) -> None:
        """Invalidate local token-exchange cache entry for current session token."""
        oauth_tokens = session.get('oauth_tokens') or {}
        subject_token = oauth_tokens.get('access_token')
        if not subject_token:
            return

        token_hash = self._subject_token_hash(str(subject_token))
        local_key = f'tx:local:{token_hash}'

        with self._user_signer_cache_lock:
            self._user_signer_cache.pop(local_key, None)
        self.app.logger.debug('cleared local token exchange signer cache for token hash=%s', token_hash)

    # Get signer for user if token exchange is enabled
    def _get_user_oci_signer(self) -> Any:
        if not self.config.get_token_exchange_enabled():
            self.app.logger.error('token exchange is disabled while user-scoped OCI calls are enabled')
            raise exceptions.ServiceUnavailable

        subject_token, expires_at = self._current_subject_token_details(require_fresh=True)
        now_epoch = int(time())
        self._prune_local_signer_cache(now_epoch)

        token_hash = self._subject_token_hash(subject_token)
        local_key = f'tx:local:{token_hash}'

        with self._user_signer_cache_lock:
            cached = self._user_signer_cache.get(local_key)
            # If cache return is truthy and expires_at is greater than now return signer
            if cached and cached[1] > now_epoch:
                self.app.logger.debug('token exchange signer cache hit for token hash=%s', token_hash)
                return cached[0]

        self.app.logger.debug('token exchange signer cache miss for token hash=%s; creating signer', token_hash)

        try:
            signer = create_user_token_exchange_signer(
                self._current_subject_token,
                self.config.get_idm_endpoint(),
                self.config.get_idm_client_id(),
                self.config.get_idm_client_secret(),
            )

            with self._user_signer_cache_lock:
                self._user_signer_cache[local_key] = (signer, expires_at)
            self.app.logger.debug(
                'cached token exchange signer locally for token hash=%s until epoch=%s',
                token_hash,
                expires_at,
            )
            return signer
        except Exception:
            self.app.logger.exception('failed creating workload identity token exchange signer')
            raise exceptions.ServiceUnavailable

    # Build clients for user if token exchange signer is enabled
    def _build_user_scoped_services(self, user_signer: Any) -> tuple[Search, Deleter, Extender]:
        user_query = QueryTags(
            self.config.get_mgmt_tag().namespace,
            self.config.get_mgmt_tag().key,
            self.config.get_cleanup_compartment(),
            log_level=self.config.get_log_level(),
        )
        user_search = Search(
            self.config.get_mgmt_tag().namespace,
            self.config.get_mgmt_tag().key,
            dict(self.cfg),
            user_signer,
            user_query,
            handler=self.config.get_log_handler(),
            log_level=self.config.get_log_level(),
        )

        if self.config.get_filter().key:
            user_search.set_filter(
                ExpiryFilter(
                    self.config.get_filter().namespace,
                    self.config.get_filter().key,
                    log_level=self.app.logger.getEffectiveLevel(),
                )
            )

        user_deleter = Deleter(
            dict(self.cfg),
            self.config.get_cleanup_compartment(),
            user_signer,
            regions=user_search.region_names,
            handler=self.config.get_log_handler(),
            log_level=self.config.get_log_level(),
        )

        user_extender = Extender(
            dict(self.cfg),
            signer=user_signer,
            tag_namespace=self.config.get_mgmt_tag().namespace,
            tag_key=self.config.get_filter().key or 'Expires',
            regions=user_search.region_names,
            handler=self.config.get_log_handler(),
            log_level=self.config.get_log_level(),
        )

        # Work requests and cost services are scoped at the app level
        return user_search, user_deleter, user_extender

    def get_oci_services(self) -> tuple[Search, Deleter, Extender]:
        if not self.config.get_user_scoped_oci_calls():
            return self.search, self.deleter, self.extender

        cached = getattr(g, 'oci_services', None)
        if cached:
            return cached

        user_signer = self._get_user_oci_signer()
        g.oci_services = self._build_user_scoped_services(user_signer)
        return g.oci_services


# initialize_service_context bootstraps the service context singleton and creates 
# default/fallback service instances.
def initialize_service_context(app: Flask, config: Configuration) -> ServiceContext:
    cfg, signer = create_signer(
        config.get_auth_type(),
        profile=config.get_profile(),
        location=config.get_config_file(),
    )
    if config.get_log_level() == 'DEBUG':
        cfg['log_requests'] = True

    query = QueryTags(
        config.get_mgmt_tag().namespace,
        config.get_mgmt_tag().key,
        config.get_cleanup_compartment(),
        log_level=config.get_log_level(),
    )

    search = Search(
        config.get_mgmt_tag().namespace,
        config.get_mgmt_tag().key,
        cfg,
        signer,
        query,
        handler=config.get_log_handler(),
        log_level=config.get_log_level(),
    )

    if config.get_filter().key:
        search.set_filter(
            ExpiryFilter(
                config.get_filter().namespace,
                config.get_filter().key,
                log_level=app.logger.getEffectiveLevel(),
            )
        )

    deleter = Deleter(
        cfg,
        config.get_cleanup_compartment(),
        signer,
        regions=search.region_names,
        handler=config.get_log_handler(),
        log_level=config.get_log_level(),
    )

    # Get full set of normalized supported delete types
    delete_supported_norm = (
        set(Deleter.supported_delete_display_map().keys()) |
        set(Deleter.supported_force_display_map().keys())
    )

    extender = Extender(
        cfg,
        signer=signer,
        tag_namespace=config.get_mgmt_tag().namespace,
        tag_key=config.get_filter().key or 'Expires',
        handler=config.get_log_handler(),
        log_level=config.get_log_level(),
    )

    # Get full set of normalized supported extender types
    extend_supported_norm = Extender.supported_extend_norm_keys()

    cost_service = CostService(
        cfg,
        signer,
        search.home_region,
        handler=config.get_log_handler(),
        log_level=config.get_log_level(),
    )
    cost_service.initialize_cache(cfg['tenancy'])

    request_chaser = WorkRequestChaser(
        cfg,
        signer,
        regions=search.region_names,
        log_level=config.get_log_level(),
        handler=config.get_log_handler(),
    )

    oauth = Authenticator(
        config.get_idm_endpoint(),
        config.get_idm_client_id(),
        config.get_idm_client_secret(),
        handler=config.get_log_handler(),
        log_level=config.get_log_level(),
    )

    return ServiceContext(
        app=app,
        config=config,
        cfg=cfg,
        signer=signer,
        search=search,
        deleter=deleter,
        extender=extender,
        cost_service=cost_service,
        request_chaser=request_chaser,
        oauth=oauth,
        delete_supported_norm=delete_supported_norm,
        extend_supported_norm=extend_supported_norm,
    )
