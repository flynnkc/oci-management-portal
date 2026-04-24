#!/usr/bin/python3.11

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict
from threading import Lock, Thread
import logging
from time import perf_counter

from datetime import timedelta
import oci

from ..utils import log_factory


class CostService:
    """
    Pulls month-to-date cost by resource OCID from OCI Usage API.
    """

    #def __init__(self, config: dict, signer) -> None:
    #    self.client = oci.usage_api.UsageapiClient(config, signer=signer)

    def __init__(self,
                 config: dict,
                 signer,
                 home_region: str,
                 cache_ttl: timedelta=timedelta(hours=1),
                 handler: logging.Handler = logging.StreamHandler(),
                 log_level: int | str = logging.INFO) -> None:
        self.logger = log_factory(__name__, log_level, handler)
        self.config = config
        self.signer = signer

        # Keep upstream calls bounded so background refreshes fail fast under network issues.
        self.client = oci.usage_api.UsageapiClient(
            config,
            signer=signer,
            retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY
        )
        self.client.base_client.set_region(home_region)

        self._cache_lock = Lock()
        self._cache_ttl = cache_ttl
        self._cache_data: Dict[str, float] = {}
        self._cache_loaded_at: datetime | None = None
        self._cache_initialized = False
        self._refresh_in_progress = False

        self.logger.debug(
            "CostService initialized region=%s timeout=%s ttl_seconds=%s",
            home_region,
            int(self._cache_ttl.total_seconds()),
        )

    @staticmethod
    def _redact_tenancy(tenancy_ocid: str) -> str:
        if not tenancy_ocid:
            return "unknown"
        if len(tenancy_ocid) <= 12:
            return tenancy_ocid
        return f"...{tenancy_ocid[-12:]}"

    @staticmethod
    def _start_of_day_utc(dt: datetime | None = None) -> datetime:
        dt = dt or datetime.now(timezone.utc)
        return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    
    @staticmethod
    def _last_30_days_start_utc() -> datetime:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=30)
        return datetime(start.year, start.month, start.day, tzinfo=timezone.utc)

    def load_current_costs(self, tenancy_ocid: str) -> Dict[str, float]:
        """
        Returns:
            {resource_ocid: month_to_date_cost}
        """
        start = self._last_30_days_start_utc()
        end = self._start_of_day_utc()
        started = perf_counter()

        self.logger.debug(
            "Cost load start tenancy=%s window_start=%s window_end=%s granularity=%s query_type=%s",
            self._redact_tenancy(tenancy_ocid),
            start.isoformat(),
            end.isoformat(),
            "DAILY",
            "COST",
        )

        details = oci.usage_api.models.RequestSummarizedUsagesDetails(
            tenant_id=tenancy_ocid,
            time_usage_started=start,
            time_usage_ended=end,
            granularity="DAILY",
            query_type="COST",
            is_aggregate_by_time=True,
            group_by=["resourceId"],
        )

        response = self.client.request_summarized_usages(
            request_summarized_usages_details=details
        )

        rows = getattr(response.data, "items", []) or []
        self.logger.debug(
            "Cost load OCI response status=%s rows=%s elapsed_ms=%.1f",
            getattr(response, "status", "unknown"),
            len(rows),
            (perf_counter() - started) * 1000,
        )

        cost_map = defaultdict(float)
        skipped_missing_fields = 0
        skipped_parse_errors = 0

        for row in rows:
            resource_id = getattr(row, "resource_id", None)
            cost = getattr(row, "computed_amount", None)

            if not resource_id or cost is None:
                skipped_missing_fields += 1
                continue

            try:
                cost_map[resource_id] += float(cost)
            except (TypeError, ValueError):
                skipped_parse_errors += 1
                continue

        self.logger.debug(
            "Cost load parsed resources=%s skipped_missing=%s skipped_parse=%s",
            len(cost_map),
            skipped_missing_fields,
            skipped_parse_errors,
        )

        return dict(cost_map)

    def _refresh_cache(self, tenancy_ocid: str) -> None:
        started = perf_counter()
        self.logger.debug(
            "Cost cache refresh started tenancy=%s",
            self._redact_tenancy(tenancy_ocid),
        )
        try:
            latest = self.load_current_costs(tenancy_ocid)
            with self._cache_lock:
                self._cache_data = latest
                self._cache_loaded_at = datetime.now(timezone.utc)
                self._cache_initialized = True
                loaded_at = self._cache_loaded_at
            self.logger.debug(
                "Cost cache refresh completed resources=%s loaded_at=%s elapsed_ms=%.1f",
                len(latest),
                loaded_at.isoformat() if loaded_at else None,
                (perf_counter() - started) * 1000,
            )
        except Exception:
            self.logger.exception(
                "Cost cache refresh failed elapsed_ms=%.1f",
                (perf_counter() - started) * 1000,
            )
        finally:
            with self._cache_lock:
                self._refresh_in_progress = False

    def initialize_cache(self, tenancy_ocid: str) -> Dict[str, float]:
        """
        Performs a synchronous first load for startup/readiness use-cases.

        Raises:
            Exception propagated from OCI usage API call/parsing failures.
        """
        started = perf_counter()
        self.logger.info("Cost cache initial load starting")
        latest = self.load_current_costs(tenancy_ocid)
        with self._cache_lock:
            self._cache_data = latest
            self._cache_loaded_at = datetime.now(timezone.utc)
            self._cache_initialized = True
            self._refresh_in_progress = False

        self.logger.info(
            "Cost cache initial load completed resources=%s elapsed_ms=%.1f",
            len(latest),
            (perf_counter() - started) * 1000,
        )
        return dict(latest)

    def is_cache_ready(self) -> bool:
        """Readiness signal for startup probes."""
        with self._cache_lock:
            return self._cache_initialized

    def _start_refresh_if_needed(self, tenancy_ocid: str) -> None:
        with self._cache_lock:
            if self._refresh_in_progress:
                self.logger.debug("Cost cache refresh skipped reason=in_progress")
                return
            self._refresh_in_progress = True

        self.logger.debug("Cost cache refresh thread starting")

        Thread(
            target=self._refresh_cache,
            args=(tenancy_ocid,),
            daemon=True,
            name="cost-cache-refresh",
        ).start()

    def get_current_costs(self, tenancy_ocid: str, force_refresh: bool = False) -> Dict[str, float]:
        """
        Stale-while-refresh behavior:
        - returns fresh cache immediately when available
        - on stale/empty cache, triggers background refresh and returns current cache
        - never blocks request path on upstream Usage API calls
        """
        now = datetime.now(timezone.utc)

        with self._cache_lock:
            cached = dict(self._cache_data)
            cache_size = len(cached)
            is_fresh = (
                self._cache_loaded_at is not None
                and (now - self._cache_loaded_at) < self._cache_ttl
            )
            cache_age_seconds = (
                (now - self._cache_loaded_at).total_seconds()
                if self._cache_loaded_at is not None
                else None
            )

        if is_fresh and not force_refresh:
            self.logger.debug(
                "Cost cache decision=return_fresh force_refresh=%s cache_size=%s cache_age_seconds=%s",
                force_refresh,
                cache_size,
                f"{cache_age_seconds:.1f}" if cache_age_seconds is not None else None,
            )
            return cached

        # For stale/empty cache (or forced refresh), refresh asynchronously and
        # fail-open by returning current cache immediately.
        self.logger.debug(
            "Cost cache decision=return_stale_refreshing force_refresh=%s cache_size=%s cache_age_seconds=%s",
            force_refresh,
            cache_size,
            f"{cache_age_seconds:.1f}" if cache_age_seconds is not None else None,
        )
        self._start_refresh_if_needed(tenancy_ocid)
        return cached
