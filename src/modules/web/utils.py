from __future__ import annotations

from collections.abc import Mapping
from http import HTTPStatus

from flask import render_template

from ..utils import log_factory


def render_service_unavailable_button() -> str:
    return render_template(
        'components/button.html',
        status=HTTPStatus.SERVICE_UNAVAILABLE,
        message='Service temporarily unavailable',
    )


def render_auth_required_button() -> str:
    return render_template(
        'components/button.html',
        status=HTTPStatus.UNAUTHORIZED,
        message='Please sign in again',
    )


def _resource_attr(resource: object, resource_dict: Mapping, *keys: str) -> str:
    for key in keys:
        value = resource_dict.get(key)
        if value:
            return value

    for key in keys:
        value = getattr(resource, key, None)
        if value:
            return value

    return ''


def log_unsupported_resources(
    app,
    source: str,
    resources: list[dict],
    *,
    normalize_resource_type,
    delete_supported_norm: set[str],
    extend_supported_norm: set[str],
) -> None:
    # Flask may install a default stream handler before the configured app
    # handler. Use the most recently added handler so module-origin logs keep
    # the same destination as the app's configured logging.
    handler = app.logger.handlers[-1] if app.logger.handlers else None
    if handler is None:
        logger = app.logger
    else:
        logger = log_factory(
            __name__,
            app.logger.getEffectiveLevel(),
            handler,
        )
    unsupported_counts: dict[str, int] = {}
    missing_type_count = 0

    for resource in resources:
        if isinstance(resource, dict):
            resource_dict = resource
        elif hasattr(resource, 'to_dict'):
            resource_dict = resource.to_dict()
        else:
            resource_dict = vars(resource)

        resource_type = _resource_attr(
            resource,
            resource_dict,
            'resource_type',
            'resourceType',
            '_resource_type',
            'type',
        )
        if not resource_type:
            missing_type_count += 1
            continue

        norm_type = normalize_resource_type(resource_type)
        delete_supported = norm_type in delete_supported_norm
        extend_supported = norm_type in extend_supported_norm
        if delete_supported and extend_supported:
            continue

        unsupported_counts[resource_type] = unsupported_counts.get(resource_type, 0) + 1

    if missing_type_count:
        logger.error(
            '[INVALID_SEARCH_RESULT] source=%s missing_resource_type count=%s',
            source,
            missing_type_count,
        )

    for resource_type, count in sorted(unsupported_counts.items()):
        logger.warning(
            '[UNSUPPORTED_RESOURCE] resource_type=%s count=%s',
            resource_type,
            count,
        )
