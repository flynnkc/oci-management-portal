#!/usr/bin/python3.11

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict
from threading import Lock, Thread
import logging

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
                 handler: logging.Handler = logging.StreamHandler(),
                 log_level: int | str = logging.INFO) -> None:
        self.logger = log_factory(__name__, log_level, handler)
        self.config = config
        self.signer = signer

        # Keep upstream calls bounded so background refreshes fail fast under network issues.
        self.client = oci.usage_api.UsageapiClient(
            config,
            signer=signer,
            timeout=(3, 8),
        )
        self.client.base_client.set_region(home_region)

        self._cache_lock = Lock()
        self._cache_ttl = timedelta(minutes=10)
        self._cache_data: Dict[str, float] = {}
        self._cache_loaded_at: datetime | None = None
        self._refresh_in_progress = False

    @staticmethod
    def _start_of_day_utc(dt: datetime | None = None) -> datetime:
        dt = dt or datetime.now(timezone.utc)
        return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)

    #@staticmethod
    #def _month_start_utc() -> datetime:
    #    now = datetime.now(timezone.utc)
    #    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    
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

        cost_map = defaultdict(float)

        for row in getattr(response.data, "items", []) or []:
            resource_id = getattr(row, "resource_id", None)
            cost = getattr(row, "computed_amount", None)

            if not resource_id or cost is None:
                continue

            try:
                cost_map[resource_id] += float(cost)
            except (TypeError, ValueError):
                continue

        return dict(cost_map)

    def _refresh_cache(self, tenancy_ocid: str) -> None:
        try:
            latest = self.load_current_costs(tenancy_ocid)
            with self._cache_lock:
                self._cache_data = latest
                self._cache_loaded_at = datetime.now(timezone.utc)
        except Exception:
            self.logger.exception("Cost cache refresh failed")
        finally:
            with self._cache_lock:
                self._refresh_in_progress = False

    def _start_refresh_if_needed(self, tenancy_ocid: str) -> None:
        with self._cache_lock:
            if self._refresh_in_progress:
                return
            self._refresh_in_progress = True

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
            is_fresh = (
                self._cache_loaded_at is not None
                and (now - self._cache_loaded_at) < self._cache_ttl
            )

        if is_fresh and not force_refresh:
            return cached

        # For stale/empty cache (or forced refresh), refresh asynchronously and
        # fail-open by returning current cache immediately.
        self._start_refresh_if_needed(tenancy_ocid)
        return cached
