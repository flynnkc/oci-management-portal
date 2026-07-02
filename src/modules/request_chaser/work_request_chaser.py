#!/usr/bin/python3.11

import logging

from oci import identity, work_requests
from oci.signer import Signer
from oci.exceptions import ServiceError
from oci.work_requests.models import WorkRequest
from oci.identity.models import TaggingWorkRequest

from ..utils import log_factory


class WorkRequestChaser:

    DELETE = 'DELETE'
    EXTEND = 'EXTEND'

    SUCCEEDED = [WorkRequest.STATUS_SUCCEEDED,
                 TaggingWorkRequest.STATUS_SUCCEEDED,
                 TaggingWorkRequest.STATUS_PARTIALLY_SUCCEEDED]
    FAILED = [WorkRequest.STATUS_FAILED,
              WorkRequest.STATUS_CANCELED,
              TaggingWorkRequest.STATUS_FAILED,
              TaggingWorkRequest.STATUS_CANCELED]

    def __init__(
            self,
            config: dict,
            signer: Signer,
            handler: logging.Handler = logging.StreamHandler(),
            log_level: int | str = logging.INFO,
            regions: list[str] | None = None) -> None:
        self.logger = log_factory(__name__, log_level, handler)
        
        self.config = config
        self.signer = signer

        self.move_client: dict[str, work_requests.WorkRequestClient] = {}
        self.tag_client: dict[str, identity.IdentityClient] = {}
        self._home_region: str | None = None

        self._set_clients(regions)

    def _set_clients(self, regions: list[str] | None):
        regions = regions or []
        if not regions:
            regions = [self.config['region']]

        for region in regions:
            regional_config = dict(self.config)
            regional_config['region'] = region
            self.move_client[region] = work_requests.WorkRequestClient(
                regional_config,
                signer=self.signer
            )
            self.tag_client[region] = identity.IdentityClient(
                regional_config,
                signer=self.signer
            )

    def _get_home_region(self) -> str:
        if self._home_region:
            return self._home_region

        tenancy_id = self.config["tenancy"]
        identity_client = identity.IdentityClient(self.config, signer=self.signer)
        tenancy = identity_client.get_tenancy(tenancy_id).data
        subscriptions = identity_client.list_region_subscriptions(tenancy_id).data
        for subscription in subscriptions:
            if subscription.region_key == tenancy.home_region_key:
                self._home_region = subscription.region_name
                return self._home_region

        raise WorkRequestChaserException("Unable to determine tenancy home region")

    def _candidate_regions(self, region: str, action: str) -> list[str]:
        candidates = [region]
        if action == WorkRequestChaser.EXTEND:
            home_region = self._get_home_region()
            if home_region not in candidates:
                candidates.append(home_region)
        return candidates

    def get_work_request(self, request_ocid: str, region: str, action: str) -> str:
        last_error: ServiceError | None = None
        for candidate_region in self._candidate_regions(region, action):
            try:
                if action == WorkRequestChaser.DELETE:
                    response = self.move_client[candidate_region].get_work_request(request_ocid)
                elif action == WorkRequestChaser.EXTEND:
                    response = self.tag_client[candidate_region].get_tagging_work_request(
                        request_ocid)
                else:
                    raise WorkRequestChaserException(
                        f"Unsupported work request action '{action}'."
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

    def get_work_request_error_summary(self, request_ocid: str, region: str, action: str) -> str:
        for candidate_region in self._candidate_regions(region, action):
            try:
                if action == WorkRequestChaser.DELETE:
                    response = self.move_client[candidate_region].list_work_request_errors(request_ocid)
                elif action == WorkRequestChaser.EXTEND:
                    response = self.tag_client[candidate_region].list_tagging_work_request_errors(request_ocid)
                else:
                    raise WorkRequestChaserException(
                        f"Unsupported work request action '{action}'."
                    )

                items = getattr(response.data, "items", []) or []
                if not items:
                    continue

                first = items[0]
                message = getattr(first, "message", None) or getattr(first, "error_message", None)
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
