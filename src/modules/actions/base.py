#!/usr/bin/python3.11
import logging
import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Optional

import oci
from oci import Signer
from oci.identity_domains import IdentityDomainsClient

from .client_bundle import ClientBundle
from .lazy_client_map import LazyClientMap
from ..utils import log_factory


class BaseAction:
    SUPPORTED_RESOURCE_TYPE_ATTRS: tuple[str, ...] = ()

    def __init__(
        self,
        config: dict[str, Any],
        signer: Any,
        handler: logging.Handler,
        log_level: int | str,
        regions=None,
        signer_factory: Callable[[str | None], Any] | None = None,
        logger_name: str | None = None,
        require_region_without_regions: bool = False,
        require_signer_for_regions: bool = True,
        allow_signer_factory_for_regions: bool = True,
        restore_signer_region_after_build: bool = True,
        signer_required_message: str = "Signer is required when creating multi-region clients",
    ):
        self.logger = log_factory(logger_name or __name__, log_level, handler)
        self.config = config
        self.signer: Signer | None = signer
        self.signer_factory = signer_factory
        self._restore_signer_region_after_build = restore_signer_region_after_build
        self.clients = self._create_clients(
            regions,
            require_region_without_regions=require_region_without_regions,
            require_signer_for_regions=require_signer_for_regions,
            allow_signer_factory_for_regions=allow_signer_factory_for_regions,
            signer_required_message=signer_required_message,
        )
        self._domain_client_cache = {}
        self._home_region = None

    @staticmethod
    def normalize_resource_type(rtype: Optional[str]) -> str:
        return re.sub(r'[_\-\s]', '', (rtype or '').strip().lower()) if rtype else ""

    def _normalize_resource_type(self, rtype: Optional[str]) -> str:
        return self.normalize_resource_type(rtype)

    @classmethod
    def supported_resource_types(cls) -> set[str]:
        resource_types: set[str] = set()

        for attr_name in cls.SUPPORTED_RESOURCE_TYPE_ATTRS:
            values = getattr(cls, attr_name, ())
            if isinstance(values, Mapping):
                values = values.keys()
            if isinstance(values, str) or not isinstance(values, Iterable):
                values = (values,)
            resource_types.update(str(value) for value in values if value)

        return resource_types

    @classmethod
    def supported_display_map(cls) -> dict[str, str]:
        """
        Returns {normalized_key: display_name} for all supported resource types.
        """
        return {
            cls.normalize_resource_type(resource_type): resource_type
            for resource_type in cls.supported_resource_types()
            if resource_type
        }

    @classmethod
    def supported_norm_keys(cls) -> set[str]:
        return set(cls.supported_display_map().keys())

    def _create_clients(
        self,
        regions,
        require_region_without_regions: bool = False,
        require_signer_for_regions: bool = True,
        allow_signer_factory_for_regions: bool = True,
        signer_required_message: str = "Signer is required when creating multi-region clients",
    ) -> dict:
        original_region = self.config.get("region")
        original_signer_region = getattr(self.signer, "region", None)
        allowed_regions = regions or ([original_region] if original_region else [])
        clients = LazyClientMap(allowed_regions, self._build_client_for_region)

        if not regions:
            if require_region_without_regions and not original_region:
                raise ValueError("Config missing 'region' for client creation")
        elif require_signer_for_regions:
            if allow_signer_factory_for_regions:
                missing_signer = self.signer is None and self.signer_factory is None
            else:
                missing_signer = self.signer is None
            if missing_signer:
                raise ValueError(signer_required_message)

        if original_region is not None:
            self.config["region"] = original_region
        if self.signer is not None and original_signer_region is not None:
            self.signer.region = original_signer_region

        return clients

    def _build_client_for_region(self, region: str) -> ClientBundle:
        if not region:
            raise ValueError("Region must be provided to build client bundle")
        region_config = self.config.copy()
        region_config["region"] = region
        signer = self.signer_factory(region) if self.signer_factory else self.signer
        original_signer_region = getattr(signer, "region", None)
        if signer is not None and not self.signer_factory:
            signer.region = region
        bundle = ClientBundle(region_config, signer)
        if (
            self._restore_signer_region_after_build
            and signer is not None
            and not self.signer_factory
            and original_signer_region is not None
        ):
            signer.region = original_signer_region
        return bundle

    def _get_tenancy_home_region_name(self):
        if self._home_region:
            return self._home_region

        if self.signer is None:
            raise ValueError("Signer is required to resolve tenancy home region")

        identity_client = oci.identity.IdentityClient(self.config, signer=self.signer)
        tenancy_id = self.config["tenancy"]
        tenancy = identity_client.get_tenancy(tenancy_id).data
        home_region_key = tenancy.home_region_key
        region_subscriptions = identity_client.list_region_subscriptions(tenancy_id).data

        for reg in region_subscriptions:
            if reg.region_key == home_region_key:
                self._home_region = reg.region_name
                return self._home_region

        raise Exception("Unable to determine tenancy home region")

    def _get_home_region_client_bundle(self) -> tuple[str, ClientBundle]:
        home_region = self._get_tenancy_home_region_name()
        if home_region not in self.clients:
            self.clients[home_region] = self._build_client_for_region(home_region)
        return home_region, self.clients[home_region]

    def _iter_identity_domain_clients(self, resource):
        resource_compartment = resource.get("compartment_id")

        identity_client = oci.identity.IdentityClient(self.config, signer=self.signer)
        domains = identity_client.list_domains(
            compartment_id=resource_compartment,
            lifecycle_state="ACTIVE",
        ).data

        for domain in domains:
            domain_region = domain.home_region
            domain_endpoint = domain.url

            if not domain_region or not domain_endpoint:
                continue

            domain_config = dict(self.config)
            domain_config["region"] = domain_region
            domain_signer = self.signer_factory(domain_region) if self.signer_factory else self.signer
            if domain_signer is not None and not self.signer_factory:
                domain_signer.region = domain_region

            yield IdentityDomainsClient(
                domain_config,
                signer=domain_signer,
                service_endpoint=domain_endpoint,
            )
