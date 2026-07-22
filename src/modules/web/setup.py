from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
from logging import Logger
from threading import Lock
from time import perf_counter
from time import time
from typing import Any, Literal

from flask import Flask, g, has_request_context, request, session
from werkzeug import exceptions

from ..config import Configuration
from ..signer import create_signer, create_user_token_exchange_signer
from ..authenticator import Authenticator
from ..search import Search, ExpiryFilter, QueryTags
from ..actions import Deleter, Extender
from ..request_chaser import WorkRequestChaser
from ..cost.cost_service import CostService
from ..utils import log_factory

OciServiceName = Literal['search', 'deleter', 'extender', 'request_chaser']
OciServiceBundle = dict[OciServiceName, Any]


def _create_app_oci_signer(
    config: Configuration,
    region: str | None = None,
) -> tuple[dict[str, Any], Any]:
    cfg, signer = create_signer(
        config.get_auth_type(),
        profile=config.get_profile(),
        location=config.get_config_file(),
    )
    if region:
        cfg = dict(cfg)
        cfg['region'] = region
    return cfg, signer


def _build_app_oci_signer_factory(
    config: Configuration,
    default_signer: Any,
    default_region: str | None = None,
) -> Callable[[str | None], Any]:
    """Return the process-wide app signer for regional app-scoped clients.

    Regional OCI clients carry their target region in their config dict; the
    app-scoped signer itself does not need to be recreated per subscribed
    region.
    """
    def signer_factory(region: str | None = None) -> Any:
        return default_signer

    return signer_factory


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
    logger: Logger
    delete_supported_norm: set[str]
    extend_supported_norm: set[str]
    _user_signer_cache: dict[str, tuple[Any, int]]
    _user_signer_cache_lock: Lock
    _user_services_cache: dict[str, tuple[OciServiceBundle, int]]
    _user_services_cache_lock: Lock

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
        self.logger = log_factory(
            __name__,
            config.get_log_level(),
            config.get_log_handler(),
        )
        self.delete_supported_norm = delete_supported_norm
        self.extend_supported_norm = extend_supported_norm
        # Process-local cache keyed by access-token hash and region. Each pod has
        # its own cache; session affinity improves hit rate without making this
        # cache part of the correctness model.
        self._user_signer_cache = {}
        self._user_signer_cache_lock = Lock()
        # Process-local cache keyed by access-token hash. The service bundle
        # contains user-scoped Search/Deleter/Extender/WorkRequestChaser
        # instances and expires with the access token that authorized their
        # signer factory.
        self._user_services_cache = {}
        self._user_services_cache_lock = Lock()

    def _request_path(self) -> str:
        return request.path if has_request_context() else '<no-request>'

    # Targeted invalidation for the current session token. Unlike a full prune,
    # this removes all regional signers and the user-scoped service bundle for
    # one token even if they have not expired; prune methods only remove expired
    # entries across the whole process-local cache.
    def clear_user_token_exchange_cache(self) -> None:
        """Invalidate process-local user-scoped OCI caches for current token."""
        oauth_tokens = session.get('oauth_tokens') or {}
        subject_token = oauth_tokens.get('access_token')
        if not subject_token:
            self.logger.debug(
                'event=upst_cache_clear status=skip reason=missing_subject_token user=%s path=%s',
                session.get('user', ''),
                self._request_path(),
            )
            return

        token_hash = self._subject_token_hash(str(subject_token))
        signer_key_prefix = f'tx:{token_hash}:'
        services_key = self._services_cache_key(str(subject_token))
        services_removed = 0
        with self._user_services_cache_lock:
            services_removed = int(self._user_services_cache.pop(services_key, None) is not None)

        with self._user_signer_cache_lock:
            stale = [key for key in self._user_signer_cache if key.startswith(signer_key_prefix)]
            for key in stale:
                self._user_signer_cache.pop(key, None)

        self.logger.debug(
            'event=upst_cache_clear status=success user=%s token_hash_prefix=%s signer_entries=%s service_entries=%s path=%s',
            session.get('user', ''),
            token_hash[:12],
            len(stale),
            services_removed,
            self._request_path(),
        )

    def get_oci_services(
        self,
        *,
        search: bool = False,
        deleter: bool = False,
        extender: bool = False,
        request_chaser: bool = False,
    ) -> OciServiceBundle:
        requested = self._requested_service_names(
            search=search,
            deleter=deleter,
            extender=extender,
            request_chaser=request_chaser,
        )
        if not self.config.get_user_scoped_oci_calls():
            self.logger.debug(
                'event=upst_user_services_cache status=bypass reason=user_scoped_disabled path=%s',
                self._request_path(),
            )
            return self._select_oci_services(self._app_scoped_service_bundle(), requested)

        return self._select_oci_services(
            self._get_user_scoped_service_bundle(),
            requested,
        )

    def _requested_service_names(
        self,
        *,
        search: bool,
        deleter: bool,
        extender: bool,
        request_chaser: bool,
    ) -> tuple[OciServiceName, ...]:
        requested: list[OciServiceName] = []
        if search:
            requested.append('search')
        if deleter:
            requested.append('deleter')
        if extender:
            requested.append('extender')
        if request_chaser:
            requested.append('request_chaser')
        if not requested:
            raise ValueError("At least one OCI service must be requested")
        return tuple(requested)

    def _select_oci_services(
        self,
        bundle: OciServiceBundle,
        service_names: tuple[OciServiceName, ...],
    ) -> OciServiceBundle:
        return {name: bundle[name] for name in service_names}

    def _app_scoped_service_bundle(self) -> OciServiceBundle:
        return {
            'search': self.search,
            'deleter': self.deleter,
            'extender': self.extender,
            'request_chaser': self.request_chaser,
        }

    def _get_user_scoped_service_bundle(self) -> OciServiceBundle:
        cached = getattr(g, 'oci_services', None)
        if cached:
            self.logger.debug(
                'event=upst_user_services_cache status=hit source=request_local user=%s path=%s',
                session.get('user', ''),
                self._request_path(),
            )
            return cached

        subject_token, expires_at = self._current_subject_token_details(require_fresh=True)
        token_hash = self._subject_token_hash(subject_token)
        now_epoch = int(time())
        cache_key = self._services_cache_key(subject_token)

        with self._user_services_cache_lock:
            pruned = self._prune_local_services_cache(now_epoch)
            if pruned:
                self.logger.debug(
                    'event=upst_user_services_cache status=prune pruned_entries=%s remaining_entries=%s path=%s',
                    pruned,
                    len(self._user_services_cache),
                    self._request_path(),
                )
            cached_services = self._user_services_cache.get(cache_key)
            if cached_services and cached_services[1] > now_epoch:
                self.logger.debug(
                    'event=upst_user_services_cache status=hit source=process_local user=%s token_hash_prefix=%s ttl_seconds=%s cache_entries=%s path=%s',
                    session.get('user', ''),
                    token_hash[:12],
                    cached_services[1] - now_epoch,
                    len(self._user_services_cache),
                    self._request_path(),
                )
                g.oci_services = cached_services[0]
                return g.oci_services

            self.logger.debug(
                'event=upst_user_services_cache status=miss user=%s token_hash_prefix=%s cache_entries=%s path=%s',
                session.get('user', ''),
                token_hash[:12],
                len(self._user_services_cache),
                self._request_path(),
            )

            started = perf_counter()
            user_signer = self._get_user_oci_signer()
            services = self._build_user_scoped_services(user_signer)
            elapsed_ms = (perf_counter() - started) * 1000
            self._user_services_cache[cache_key] = (services, expires_at)
            self.logger.info(
                'event=upst_user_services_create status=success user=%s token_hash_prefix=%s ttl_seconds=%s cache_entries=%s elapsed_ms=%.1f path=%s',
                session.get('user', ''),
                token_hash[:12],
                expires_at - now_epoch,
                len(self._user_services_cache),
                elapsed_ms,
                self._request_path(),
            )
            g.oci_services = services
            return g.oci_services

    def _subject_token_hash(self, subject_token: str) -> str:
        return sha256(subject_token.encode('utf-8')).hexdigest()

    def _signer_cache_region_key(self, region: str | None) -> str:
        return region or '__default__'

    def _signer_cache_key(self, subject_token: str, region: str | None) -> str:
        return f'tx:{self._subject_token_hash(subject_token)}:{self._signer_cache_region_key(region)}'

    def _services_cache_key(self, subject_token: str) -> str:
        return f'svc:{self._subject_token_hash(subject_token)}'

    def _prune_local_signer_cache(self, now_epoch: int) -> int:
        stale = [key for key, (_, expires_at) in self._user_signer_cache.items() if expires_at <= now_epoch]
        for key in stale:
            self._user_signer_cache.pop(key, None)
        return len(stale)

    def _prune_local_services_cache(self, now_epoch: int) -> int:
        stale = [key for key, (_, expires_at) in self._user_services_cache.items() if expires_at <= now_epoch]
        for key in stale:
            self._user_services_cache.pop(key, None)
        return len(stale)

    def _current_subject_token_details(self, require_fresh: bool = True) -> tuple[str, int]:
        """Return current subject token and its absolute expiry epoch seconds.

        If expiry metadata is missing, treat as immediately expiring for TTL
        purposes.
        """
        oauth_tokens = session.get('oauth_tokens') or {}
        subject_token = oauth_tokens.get('access_token')
        if not subject_token:
            self.logger.warning('missing oauth access token in server session during OCI token exchange')
            raise exceptions.Unauthorized

        issued_at = int(oauth_tokens.get('issued_at') or 0)
        expires_in = int(oauth_tokens.get('expires_in') or 0)
        skew = self.config.get_token_exchange_expiry_skew_seconds()
        expires_at = (issued_at + expires_in) if (issued_at and expires_in) else int(time())

        if require_fresh and issued_at and expires_in and (expires_at - skew) <= int(time()):
            self.logger.warning('oauth access token expired or near expiry for current session')
            raise exceptions.Unauthorized

        return str(subject_token), int(expires_at)

    # Returns the current OAuth access token for the user session.
    def _current_subject_token(self) -> str:
        subject_token, _ = self._current_subject_token_details(require_fresh=True)
        return subject_token

    # Get token-exchange signer for the current user session.
    def _get_user_oci_signer(self, region: str | None = None) -> Any:
        subject_token, expires_at = self._current_subject_token_details(require_fresh=True)
        token_hash = self._subject_token_hash(subject_token)
        now_epoch = int(time())
        cache_key = self._signer_cache_key(subject_token, region)
        cache_region = self._signer_cache_region_key(region)

        with self._user_signer_cache_lock:
            pruned = self._prune_local_signer_cache(now_epoch)
            if pruned:
                self.logger.debug(
                    'event=upst_token_exchange_signer_cache status=prune pruned_entries=%s remaining_entries=%s path=%s',
                    pruned,
                    len(self._user_signer_cache),
                    self._request_path(),
                )
            cached = self._user_signer_cache.get(cache_key)
            if cached and cached[1] > now_epoch:
                self.logger.debug(
                    'event=upst_token_exchange_signer_cache status=hit user=%s token_hash_prefix=%s region=%s ttl_seconds=%s cache_entries=%s path=%s',
                    session.get('user', ''),
                    token_hash[:12],
                    cache_region,
                    cached[1] - now_epoch,
                    len(self._user_signer_cache),
                    self._request_path(),
                )
                return cached[0]

            self.logger.debug(
                'event=upst_token_exchange_signer_cache status=miss user=%s token_hash_prefix=%s region=%s cache_entries=%s path=%s',
                session.get('user', ''),
                token_hash[:12],
                cache_region,
                len(self._user_signer_cache),
                self._request_path(),
            )

            started = perf_counter()
            try:
                signer = create_user_token_exchange_signer(
                    self._current_subject_token,
                    self.config.get_idm_endpoint(),
                    self.config.get_idm_client_id(),
                    self.config.get_idm_client_secret(),
                    region=region,
                )
                elapsed_ms = (perf_counter() - started) * 1000
                self._user_signer_cache[cache_key] = (signer, expires_at)
                self.logger.info(
                    'event=upst_token_exchange_signer_create status=success user=%s token_hash_prefix=%s region=%s ttl_seconds=%s cache_entries=%s elapsed_ms=%.1f path=%s',
                    session.get('user', ''),
                    token_hash[:12],
                    cache_region,
                    expires_at - now_epoch,
                    len(self._user_signer_cache),
                    elapsed_ms,
                    self._request_path(),
                )
                return signer
            except Exception:
                elapsed_ms = (perf_counter() - started) * 1000
                self.logger.exception(
                    'event=upst_token_exchange_signer_create status=failure user=%s token_hash_prefix=%s region=%s elapsed_ms=%.1f path=%s',
                    session.get('user', ''),
                    token_hash[:12],
                    cache_region,
                    elapsed_ms,
                    self._request_path(),
                )
                raise exceptions.ServiceUnavailable

    # Build clients backed by the current user's token-exchange signer.
    def _build_user_scoped_services(self, user_signer: Any) -> OciServiceBundle:
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
            signer_factory=self._get_user_oci_signer,
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
            signer_factory=self._get_user_oci_signer,
        )

        user_extender = Extender(
            dict(self.cfg),
            signer=user_signer,
            tag_namespace=self.config.get_mgmt_tag().namespace,
            tag_key=self.config.get_filter().key or 'Expires',
            regions=user_search.region_names,
            handler=self.config.get_log_handler(),
            log_level=self.config.get_log_level(),
            signer_factory=self._get_user_oci_signer,
        )

        user_request_chaser = WorkRequestChaser(
            dict(self.cfg),
            user_signer,
            regions=user_search.region_names,
            log_level=self.config.get_log_level(),
            handler=self.config.get_log_handler(),
            signer_factory=self._get_user_oci_signer,
            initialize_clients=False,
        )

        # Cost services remain scoped at the app level.
        return {
            'search': user_search,
            'deleter': user_deleter,
            'extender': user_extender,
            'request_chaser': user_request_chaser,
        }


# initialize_service_context bootstraps the service context singleton and creates 
# default/fallback service instances.
def initialize_service_context(app: Flask, config: Configuration) -> ServiceContext:
    cfg, signer = _create_app_oci_signer(config)
    app_signer_factory = _build_app_oci_signer_factory(
        config,
        signer,
        default_region=cfg.get('region'),
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
        signer_factory=app_signer_factory,
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
        signer_factory=app_signer_factory,
    )

    # Get full set of normalized supported delete types
    delete_supported_norm = Deleter.supported_norm_keys()

    extender = Extender(
        cfg,
        signer=signer,
        tag_namespace=config.get_mgmt_tag().namespace,
        tag_key=config.get_filter().key or 'Expires',
        regions=search.region_names,
        handler=config.get_log_handler(),
        log_level=config.get_log_level(),
        signer_factory=app_signer_factory,
    )

    # Get full set of normalized supported extender types
    extend_supported_norm = Extender.supported_norm_keys()

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
        signer_factory=app_signer_factory,
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
