#!/usr/bin/python3.11
import inspect
import logging
import pkgutil
from collections.abc import Callable
from functools import cache
from importlib import import_module
from typing import Any, Optional

import oci
from oci import Signer
from oci.identity_domains import IdentityDomainsClient

from .types import (
    ActionKind,
    ActionStrategy,
    BaseResourceType,
    ResourceActionSpec,
    ResourceActionRegistry,
    normalize_resource_type,
)
from .client_bundle import ClientBundle
from .lazy_client_map import LazyClientMap
from ..utils import log_factory


class BaseAction:
    # Subclasses set ACTION_KIND to the operation they expose, and
    # ACTION_SPEC_MODULES to packages containing BaseResourceType plugin classes.
    # This keeps Deleter/Extender as stable orchestration entry points while
    # allowing new OCI resource support to be contributed as isolated type files.
    ACTION_KIND: ActionKind | None = None
    ACTION_SPECS: tuple[ResourceActionSpec, ...] = ()
    ACTION_SPEC_MODULES: tuple[str, ...] = ()

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
        signer_required_message: str = (
            "signer_factory is required when creating clients for multiple regions"
        ),
    ):
        self.logger = log_factory(logger_name or __name__, log_level, handler)
        self.config = config
        self.signer: Signer | None = signer
        self.signer_factory = signer_factory
        self.clients = self._create_clients(
            regions,
            require_region_without_regions=require_region_without_regions,
            require_signer_for_regions=require_signer_for_regions,
            signer_required_message=signer_required_message,
        )
        self._domain_client_cache = {}
        self._home_region = None

    @staticmethod
    def normalize_resource_type(rtype: Optional[str]) -> str:
        return normalize_resource_type(rtype)

    @classmethod
    def _loaded_action_specs(cls) -> tuple[ResourceActionSpec, ...]:
        return cls._resource_registry().specs()

    @classmethod
    def _iter_type_modules(cls, module_name: str):
        # Accept either a single module or a package. For packages, import every
        # non-private child module so dropping actions/types/foo.py is enough to
        # make FooResource discoverable.
        module = import_module(module_name)
        yield module
        if hasattr(module, "__path__"):
            for module_info in pkgutil.iter_modules(module.__path__, f"{module.__name__}."):
                if module_info.name.rsplit(".", 1)[-1].startswith("_"):
                    continue
                yield import_module(module_info.name)

    @classmethod
    @cache
    def _resource_registry(cls) -> ResourceActionRegistry:
        registry = ResourceActionRegistry()
        for module_name in cls.ACTION_SPEC_MODULES:
            for module in cls._iter_type_modules(module_name):
                for _, resource_type in inspect.getmembers(module, inspect.isclass):
                    # Only register classes defined in the plugin module itself.
                    # This avoids re-registering imported base/helper classes.
                    if (
                        issubclass(resource_type, BaseResourceType)
                        and resource_type is not BaseResourceType
                        and resource_type.__module__ == module.__name__
                    ):
                        registry.register_type(resource_type)
        return registry

    @classmethod
    @cache
    def action_specs(cls) -> tuple[ResourceActionSpec, ...]:
        # Return only the specs relevant to this action class. The same
        # BaseResourceType can support both delete and extend, but Deleter should
        # only advertise/execute delete specs and Extender only extend specs.
        specs = cls.ACTION_SPECS + cls._loaded_action_specs()
        if cls.ACTION_KIND is None:
            return specs
        return tuple(spec for spec in specs if spec.action == cls.ACTION_KIND)

    @classmethod
    @cache
    def resource_type_map(cls) -> dict[str, type[BaseResourceType]]:
        resource_types: dict[str, type[BaseResourceType]] = {}
        for resource_type in cls._resource_registry().resource_types():
            # Keep the runtime map scoped to the action. A resource may exist in
            # actions/types/ but intentionally support only delete or only extend.
            if cls.ACTION_KIND == ActionKind.DELETE and not resource_type.delete_strategy:
                continue
            if cls.ACTION_KIND == ActionKind.EXTEND and not resource_type.extend_strategy:
                continue
            for norm in resource_type.normalized_names():
                existing = resource_types.get(norm)
                if existing is not None and existing != resource_type:
                    raise ValueError(
                        f"Duplicate resource type registration for {resource_type.resource_type}"
                    )
                resource_types[norm] = resource_type
        return resource_types

    @classmethod
    def get_resource_type(cls, resource_type: Optional[str]) -> type[BaseResourceType] | None:
        return cls.resource_type_map().get(cls.normalize_resource_type(resource_type))

    @classmethod
    def supported_resource_types(cls) -> set[str]:
        return {
            resource_type
            for spec in cls.action_specs()
            for resource_type in (spec.resource_type, *spec.aliases)
            if resource_type
        }

    @classmethod
    def supported_display_map(cls) -> dict[str, str]:
        """
        Returns {normalized_key: display_name} for all supported resource types.
        """
        display_map: dict[str, str] = {}
        for spec in cls.action_specs():
            display_map[cls.normalize_resource_type(spec.resource_type)] = spec.label
            for alias in spec.aliases:
                display_map[cls.normalize_resource_type(alias)] = spec.label
        return display_map

    @classmethod
    def supported_norm_keys(cls) -> set[str]:
        return set(cls.supported_display_map().keys())

    @classmethod
    def supported_strategy_norm_keys(cls, strategy: ActionStrategy) -> set[str]:
        return {
            cls.normalize_resource_type(resource_type)
            for spec in cls.action_specs()
            if spec.strategy == strategy
            for resource_type in (spec.resource_type, *spec.aliases)
            if resource_type
        }

    @classmethod
    @cache
    def action_spec_map(cls) -> dict[str, ResourceActionSpec]:
        spec_map: dict[str, ResourceActionSpec] = {}
        for spec in cls.action_specs():
            for resource_type in (spec.resource_type, *spec.aliases):
                norm = cls.normalize_resource_type(resource_type)
                existing = spec_map.get(norm)
                if existing is not None and existing != spec:
                    raise ValueError(
                        f"Duplicate action spec registration for {resource_type}"
                    )
                spec_map[norm] = spec
        return spec_map

    @classmethod
    def get_action_spec(cls, resource_type: Optional[str]) -> ResourceActionSpec | None:
        return cls.action_spec_map().get(cls.normalize_resource_type(resource_type))

    def _create_clients(
        self,
        regions,
        require_region_without_regions: bool = False,
        require_signer_for_regions: bool = True,
        signer_required_message: str = (
            "signer_factory is required when creating clients for multiple regions"
        ),
    ) -> dict:
        original_region = self.config.get("region")
        allowed_regions = regions or ([original_region] if original_region else [])
        clients = LazyClientMap(allowed_regions, self._build_client_for_region)

        if not regions:
            if require_region_without_regions and not original_region:
                raise ValueError("Config missing 'region' for client creation")
        elif require_signer_for_regions:
            multiple_regions = len(set(regions)) > 1
            if multiple_regions and self.signer_factory is None:
                raise ValueError(signer_required_message)
            if not multiple_regions and self.signer is None and self.signer_factory is None:
                raise ValueError("Signer or signer_factory is required for client creation")

        if original_region is not None:
            self.config["region"] = original_region

        return clients

    def _build_client_for_region(self, region: str) -> ClientBundle:
        if not region:
            raise ValueError("Region must be provided to build client bundle")
        region_config = self.config.copy()
        region_config["region"] = region
        signer = self._signer_for_region(region)
        return ClientBundle(region_config, signer)

    def _signer_for_region(self, region: str):
        if self.signer_factory is not None:
            return self.signer_factory(region)

        configured_region = self.config.get("region")
        if configured_region and region != configured_region:
            raise ValueError(
                "signer_factory is required when building a client outside "
                f"the configured region ({configured_region} -> {region})"
            )

        return self.signer

    def _signer_for_config_region(self, purpose: str):
        configured_region = self.config.get("region")
        if configured_region:
            signer = self._signer_for_region(configured_region)
        else:
            signer = self.signer

        if signer is None:
            raise ValueError(
                f"Signer or signer_factory is required to {purpose}"
            )

        return signer

    def _get_tenancy_home_region_name(self):
        if self._home_region:
            return self._home_region

        signer = self._signer_for_config_region("resolve tenancy home region")
        identity_client = oci.identity.IdentityClient(self.config, signer=signer)
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

        signer = self._signer_for_config_region("list identity domains")
        identity_client = oci.identity.IdentityClient(self.config, signer=signer)
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
            domain_signer = self._signer_for_region(domain_region)

            yield IdentityDomainsClient(
                domain_config,
                signer=domain_signer,
                service_endpoint=domain_endpoint,
            )
