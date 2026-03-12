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
            regions: list[str] = []) -> None:
        self.logger = log_factory(__name__, log_level, handler)
        
        self.config = config
        self.signer = signer

        self.move_client: dict[str, work_requests.WorkRequestClient] = {}
        self.tag_client: dict[str, identity.IdentityClient] = {}

        self._set_clients(regions)

    def _set_clients(self, regions: list[str]):
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

    def get_work_request(self, request_ocid: str, region: str, action: str) -> str:
        try:
            if action == WorkRequestChaser.DELETE:
                response = self.move_client[region].get_work_request(request_ocid)
            elif action == WorkRequestChaser.EXTEND:
                response = self.tag_client[region].get_tagging_work_request(
                    request_ocid)
            else:
                raise WorkRequestChaserException(
                    f"Unsupported work request action '{action}'."
                )
            
            self.logger.debug(f'get_work_request response: {response.data.status}')
            return response.data.status
        except ServiceError as e:
            if e.status == 404:
                self.logger.warning(
                    f'service error getting {action} work request: {e}')
                self.logger.debug(f'\tocid: {request_ocid}\n\tregion:{region}')
                return work_requests.models.WorkRequest.STATUS_IN_PROGRESS
            else:
                self.logger.error(
                    f'exception raised getting {action} work request: {e}')
                return work_requests.models.WorkRequest.STATUS_FAILED


class WorkRequestChaserException(Exception):
    """Generic exception raised for WorkRequestChaser errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
