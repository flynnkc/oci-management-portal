#!/usr/bin/python3.11

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict
from threading import Lock

from datetime import timedelta
import oci


class CostService:
    """
    Pulls month-to-date cost by resource OCID from OCI Usage API.
    """

    #def __init__(self, config: dict, signer) -> None:
    #    self.client = oci.usage_api.UsageapiClient(config, signer=signer)

    def __init__(self, config: dict, signer, home_region: str) -> None:
        self.config = config
        self.signer = signer

        self.client = oci.usage_api.UsageapiClient(config, signer=signer)
        self.client.base_client.set_region(home_region)

        self._cache_lock = Lock()
        self._cache_ttl = timedelta(minutes=10)
        self._cache_data: Dict[str, float] = {}
        self._cache_loaded_at: datetime | None = None

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

    def get_current_costs(self, tenancy_ocid: str, force_refresh: bool = False) -> Dict[str, float]:
        now = datetime.now(timezone.utc)

        with self._cache_lock:
            is_fresh = (
                self._cache_loaded_at is not None
                and (now - self._cache_loaded_at) < self._cache_ttl
            )
            if not force_refresh and is_fresh:
                return dict(self._cache_data)

        try:
            latest = self.load_current_costs(tenancy_ocid)
        except Exception:
            # Fail-open: return stale cache if available; otherwise empty mapping.
            with self._cache_lock:
                return dict(self._cache_data)

        with self._cache_lock:
            self._cache_data = latest
            self._cache_loaded_at = now
            return dict(self._cache_data)
