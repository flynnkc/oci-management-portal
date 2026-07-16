#!/usr/bin/python3.11

import logging

from collections.abc import Callable
from typing import Any, ClassVar

from oci import identity, work_requests
from oci.signer import Signer
from oci.exceptions import ServiceError
from oci.work_requests.models import WorkRequest
from oci.identity.models import TaggingWorkRequest

from ..utils import log_factory


class WorkRequestChaser:
    """Poll OCI work requests across resource and home-region endpoints."""

    DELETE: ClassVar[str] = 'DELETE'
    EXTEND: ClassVar[str] = 'EXTEND'

    SUCCEEDED: ClassVar[tuple[str, ...]] = (
        WorkRequest.STATUS_SUCCEEDED,
        TaggingWorkRequest.STATUS_SUCCEEDED,
        TaggingWorkRequest.STATUS_PARTIALLY_SUCCEEDED,
    )
    FAILED: ClassVar[tuple[str, ...]] = (
        WorkRequest.STATUS_FAILED,
        WorkRequest.STATUS_CANCELED,
        TaggingWorkRequest.STATUS_FAILED,
        TaggingWorkRequest.STATUS_CANCELED,
    )

    def __init__(
            self,
            config: dict,
            signer: Signer,
            handler: logging.Handler | None = None,
            log_level: int | str = logging.INFO,
            regions: list[str] | None = None,
            signer_factory: Callable[[str | None], Signer] | None = None,
            initialize_clients: bool = True) -> None:
        """Create work-request clients.

        When ``initialize_clients`` is true, clients are created immediately for
        each supplied region. When false, regional clients are created on first
        poll; this is used for user-scoped token-exchange signers so we do not
        exchange tokens for every subscribed region up front.
        """
        self.logger = log_factory(__name__, log_level, handler or logging.StreamHandler())

        self.config = config
        self.signer = signer
        self.signer_factory = signer_factory

        self.move_client: dict[str, work_requests.WorkRequestClient] = {}
        self.tag_client: dict[str, identity.IdentityClient] = {}
        self._home_region: str | None = None

        self._set_clients(regions, initialize_clients=initialize_clients)

    def _set_clients(
        self,
        regions: list[str] | None,
        initialize_clients: bool = True,
    ) -> None:
        """Initialize or validate the configured regional client set."""
        regions = regions or []
        if not regions:
            regions = [self._configured_region()]

        for region in regions:
            if initialize_clients:
                self._ensure_region_clients(region)
            else:
                self._validate_region_signer(region)

    def _ensure_region_clients(self, region: str) -> None:
        """Create and cache work-request clients for a region when missing."""
        if region in self.move_client and region in self.tag_client:
            return

        regional_config = dict(self.config)
        regional_config['region'] = region
        regional_signer = self._signer_for_region(region)
        self.move_client[region] = work_requests.WorkRequestClient(
            regional_config,
            signer=regional_signer
        )
        self.tag_client[region] = identity.IdentityClient(
            regional_config,
            signer=regional_signer
        )

    def _signer_for_region(self, region: str) -> Any:
        """Return a signer that can call OCI in the requested region."""
        if self.signer_factory is not None:
            return self.signer_factory(region)

        self._validate_region_signer(region)
        return self.signer

    def _validate_region_signer(self, region: str) -> None:
        """Ensure the fallback signer is only used in its configured region."""
        if self.signer_factory is not None:
            return

        configured_region = self._configured_region()
        if configured_region and region != configured_region:
            raise WorkRequestChaserException(
                "signer_factory is required when building work request clients "
                f"outside the configured region ({configured_region} -> {region})"
            )

    def _configured_region(self) -> str:
        """Return the config region as a validated string."""
        region = self.config.get('region')
        if not isinstance(region, str) or not region:
            raise WorkRequestChaserException("Unable to determine configured region")
        return region

    def _get_home_region(self) -> str:
        """Resolve and cache the tenancy home region."""
        if self._home_region:
            return self._home_region

        tenancy_id = self.config["tenancy"]
        identity_client = identity.IdentityClient(
            self.config,
            signer=self._signer_for_region(self._configured_region()),
        )
        tenancy = identity_client.get_tenancy(tenancy_id).data
        subscriptions = identity_client.list_region_subscriptions(tenancy_id).data
        for subscription in subscriptions:
            if subscription.region_key == tenancy.home_region_key:
                home_region = getattr(subscription, 'region_name', None)
                if not isinstance(home_region, str) or not home_region:
                    continue
                self._home_region = home_region
                return self._home_region

        raise WorkRequestChaserException("Unable to determine tenancy home region")

    def _candidate_regions(self, region: str, action: str) -> list[str]:
        """Return regions that may own the work request for this action."""
        candidates = [region]
        if action in {WorkRequestChaser.DELETE, WorkRequestChaser.EXTEND}:
            # Identity-backed operations can emit work requests in the tenancy
            # home region even when the affected resource is regional.
            home_region = self._get_home_region()
            if home_region not in candidates:
                candidates.append(home_region)
        for candidate_region in candidates:
            # Lazy user-scoped chasers materialize clients at poll time.
            self._ensure_region_clients(candidate_region)
        return candidates

    def get_work_request(self, request_ocid: str, region: str, action: str) -> str:
        """Return the current status for a work request."""
        last_error: ServiceError | None = None
        for candidate_region in self._candidate_regions(region, action):
            try:
                if action == WorkRequestChaser.DELETE:
                    response = self.move_client[candidate_region].get_work_request(
                        request_ocid,
                    )
                elif action == WorkRequestChaser.EXTEND:
                    response = self.tag_client[candidate_region].get_tagging_work_request(
                        request_ocid,
                    )
                else:
                    raise WorkRequestChaserException(
                        f"Unsupported work request action '{action}'.",
                    )

                self.logger.debug(
                    'get_work_request response: %s region=%s',
                    response.data.status,
                    candidate_region,
                )
                return response.data.status
            except ServiceError as e:
                last_error = e
                if e.status == 404:
                    # Some OCI APIs return the work request from a different
                    # endpoint; try the next candidate before declaring failure.
                    self.logger.warning(
                        'service error getting %s work request in region %s: %s',
                        action,
                        candidate_region,
                        e,
                    )
                    continue

                self.logger.error(
                    'exception raised getting %s work request in region %s: %s',
                    action,
                    candidate_region,
                    e,
                )
                return work_requests.models.WorkRequest.STATUS_FAILED

        if last_error is not None and last_error.status == 404:
            return work_requests.models.WorkRequest.STATUS_IN_PROGRESS
        return work_requests.models.WorkRequest.STATUS_FAILED

    def get_work_request_error_summary(
        self,
        request_ocid: str,
        region: str,
        action: str,
    ) -> str:
        """Return the first available work-request error message."""
        for candidate_region in self._candidate_regions(region, action):
            try:
                if action == WorkRequestChaser.DELETE:
                    response = self.move_client[candidate_region].list_work_request_errors(
                        request_ocid,
                    )
                elif action == WorkRequestChaser.EXTEND:
                    response = self.tag_client[
                        candidate_region
                    ].list_tagging_work_request_errors(
                        request_ocid,
                    )
                else:
                    raise WorkRequestChaserException(
                        f"Unsupported work request action '{action}'.",
                    )

                items = getattr(response.data, "items", []) or []
                if not items:
                    continue

                first = items[0]
                message = (
                    getattr(first, "message", None)
                    or getattr(first, "error_message", None)
                )
                if message:
                    return str(message)
            except ServiceError as e:
                if e.status == 404:
                    continue
                self.logger.warning(
                    'failed to fetch work request error summary action=%s region=%s error=%s',
                    action,
                    candidate_region,
                    e,
                )
                continue

        return ""


class WorkRequestChaserException(Exception):
    """Generic exception raised for WorkRequestChaser errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
