from __future__ import annotations

import argparse
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any

from oci import resource_search, usage_api
from oci.identity import IdentityClient
from oci.exceptions import ServiceError
from oci.identity.models import RegionSubscription
from oci.ons import NotificationDataPlaneClient
from oci.ons.models import MessageDetails

from ..config import Configuration
from ..search.filter import ExpiryFilter
from ..signer import create_signer


LIFECYCLE_EXCLUSIONS = (
    "TERMINATED",
    "TERMINATING",
    "DELETED",
)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _configured_regions(cfg: dict[str, Any], signer: Any, configured: str) -> list[str]:
    if configured:
        return _split_csv(configured)

    client = IdentityClient(cfg, signer=signer)
    response = client.list_region_subscriptions(cfg["tenancy"])
    return sorted(
        region.region_name
        for region in response.data
        if region.status == RegionSubscription.STATUS_READY
    )


def _search_query(config: Configuration) -> str:
    exclusions = " && ".join(
        f"lifeCycleState != '{state}'" for state in LIFECYCLE_EXCLUSIONS
    )
    return (
        "query all resources where "
        f"(definedTags.namespace = '{config.get_filter().namespace}' && "
        f"definedTags.key = '{config.get_filter().key}') && "
        f"compartmentid != '{config.get_cleanup_compartment()}' && "
        f"{exclusions}"
    )


def _defined_tag(item: Any, namespace: str, key: str) -> str:
    defined_tags = getattr(item, "defined_tags", None) or {}
    try:
        return str((defined_tags.get(namespace) or {}).get(key) or "").strip()
    except AttributeError:
        return ""


def _find_expired_resources(config: Configuration, logger: logging.Logger) -> list[dict[str, str]]:
    cfg, signer = create_signer(
        config.get_auth_type(),
        profile=config.get_profile(),
        location=config.get_config_file(),
    )
    details = resource_search.models.StructuredSearchDetails(query=_search_query(config))
    expiry_filter = ExpiryFilter(
        config.get_filter().namespace,
        config.get_filter().key,
        log_level=logger.getEffectiveLevel(),
    )
    regions = _configured_regions(cfg, signer, _env("OCI_MGMT_DASH_REPORT_REGIONS"))
    resources: list[dict[str, str]] = []
    seen: set[str] = set()

    for region in regions:
        regional_cfg = dict(cfg)
        regional_cfg["region"] = region
        client = resource_search.ResourceSearchClient(regional_cfg, signer=signer)
        next_page = None

        while True:
            response = client.search_resources(details, page=next_page, limit=1000)
            response = expiry_filter.results(response)

            for item in response.data.items or []:
                identifier = getattr(item, "identifier", "") or ""
                if not identifier or identifier in seen:
                    continue
                owner = _defined_tag(
                    item,
                    config.get_mgmt_tag().namespace,
                    config.get_mgmt_tag().key,
                )
                if not owner:
                    continue
                expiry = _defined_tag(
                    item,
                    config.get_filter().namespace,
                    config.get_filter().key,
                )
                # ExpiryFilter deliberately retains malformed tags; reports must not
                # describe those resources as confirmed expired.
                try:
                    if datetime.strptime(expiry, "%Y-%m-%d").date() >= datetime.now(timezone.utc).date():
                        continue
                except ValueError:
                    continue
                seen.add(identifier)
                resources.append({
                    "display_name": getattr(item, "display_name", "") or "",
                    "identifier": getattr(item, "identifier", "") or "",
                    "resource_type": getattr(item, "resource_type", "") or "",
                    "region": region,
                    "compartment_id": getattr(item, "compartment_id", "") or "",
                    "lifecycle_state": getattr(item, "lifecycle_state", "") or "",
                    "owner": owner,
                    "expiry": expiry,
                })

            next_page = response.next_page
            if not next_page:
                break

        logger.info("Expired resource report searched region=%s total_matches=%d", region, len(resources))

    return resources


def _load_report_costs(config: Configuration):
    """Fetch all cost pages for the previous 30 complete UTC days."""
    cfg, signer = create_signer(config.get_auth_type(), profile=config.get_profile(),
                                location=config.get_config_file())
    subscriptions = IdentityClient(cfg, signer=signer).list_region_subscriptions(cfg["tenancy"]).data
    home_region = next(region.region_name for region in subscriptions if region.is_home_region)
    client = usage_api.UsageapiClient(dict(cfg, region=home_region), signer=signer)
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=30)
    details = usage_api.models.RequestSummarizedUsagesDetails(
        tenant_id=cfg["tenancy"], time_usage_started=start, time_usage_ended=end,
        granularity="DAILY", query_type="COST", is_aggregate_by_time=True,
        group_by=["resourceId"],
    )
    costs = {}
    currencies = set()
    page = None
    while True:
        response = client.request_summarized_usages(details, page=page)
        for row in response.data.items or []:
            if not row.resource_id or row.computed_amount is None:
                continue
            currency = row.currency or "unspecified currency"
            currencies.add(currency)
            amount = Decimal(str(row.computed_amount))
            if not amount.is_finite():
                raise ValueError("Non-finite cost returned by OCI Usage API")
            previous = costs.get(row.resource_id, (Decimal(0), currency))
            costs[row.resource_id] = (previous[0] + amount, currency)
        page = response.next_page
        if not page:
            break
    if len(currencies) > 1:
        raise ValueError("Cannot rank costs across multiple currencies without conversion")
    return costs, start, end


def _summary_by_owner(resources: list[dict[str, str]]) -> list[str]:
    counts: dict[str, int] = defaultdict(int)
    for item in resources:
        owner = item["owner"] or "unassigned"
        counts[owner] += 1
    return [f"- {owner}: {count}" for owner, count in sorted(counts.items())]


def _add_compartment_names(config: Configuration, resources: list[dict[str, str]]) -> None:
    """Resolve each distinct compartment once; retain an identifiable fallback."""
    cfg, signer = create_signer(config.get_auth_type(), profile=config.get_profile(),
                                location=config.get_config_file())
    client = IdentityClient(cfg, signer=signer)
    names: dict[str, str] = {}
    for item in resources:
        compartment_id = item.get("compartment_id", "")
        if not compartment_id:
            item["compartment_name"] = "Not available"
            continue
        if compartment_id not in names:
            try:
                names[compartment_id] = client.get_compartment(compartment_id).data.name
            except ServiceError as exc:
                if exc.status not in (403, 404):
                    raise
                logging.getLogger(__name__).warning(
                    "Cannot resolve compartment %s: %s", compartment_id, exc.code)
                names[compartment_id] = f"Name unavailable ({compartment_id})"
        item["compartment_name"] = names[compartment_id]


def _build_message(resources: list[dict[str, str]], app_uri: str, max_items: int,
                   costs: dict, start: datetime, end: datetime) -> str:
    resources = [item for item in resources if item.get("owner", "").strip()]
    ranked = sorted(
        (item for item in resources if item["identifier"] in costs),
        key=lambda item: (-costs[item["identifier"]][0], item["identifier"]),
    )
    max_items = min(25, max(1, max_items))
    lines = [
        "OCI RESOURCE EXPIRY REPORT",
        "=========================",
        "Tenancy-wide summary",
        "",
        f"Total Expired resources: {len(resources):,}",
        f"Generated: {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M UTC')}",
        f"Cost period: {start:%d %b %Y} to {end - timedelta(days=1):%d %b %Y} (UTC, 30 complete days)",
    ]
    if app_uri:
        lines.append(f"Portal: {app_uri}")

    lines.extend(["", f"TOP {min(max_items, len(ranked))} EXPIRED RESOURCES BY COST",
                  "Highest cost first", "----------------------------------------"])
    rows = [["#", "Resource name", "Type", "Compartment", "Owner", "Cost"]]
    for index, item in enumerate(ranked[:max_items], 1):
        amount, currency = costs[item["identifier"]]
        name = " ".join((item['display_name'] or 'Unnamed resource').split())
        owner = " ".join((item['owner'] or 'Unassigned').split())
        resource_type = " ".join((item.get('resource_type') or 'Unknown').split())
        compartment = " ".join((item.get('compartment_name') or item.get('compartment_id') or 'Not available').split())
        # Keep full names and owner tags; remove separators embedded in values
        # so each resource remains a single, unambiguous table row.
        rows.append([str(index), name.replace('|', '/'), resource_type.replace('|', '/'),
                     compartment.replace('|', '/'), owner.replace('|', '/'),
                     f"{currency} {amount:,.2f}"])

    if ranked:
        widths = [max(len(row[col]) for row in rows) for col in range(len(rows[0]))]
        def table_row(row):
            return " | ".join(value.rjust(widths[col]) if col in (0, 5)
                              else value.ljust(widths[col]) for col, value in enumerate(row))
        lines.append(table_row(rows[0]))
        lines.append("-+-".join("-" * width for width in widths))
        lines.extend(table_row(row) for row in rows[1:])
        lines.append("")

    if not ranked:
        lines.append("No resource-level cost data available for these expired resources.")

    lines.extend(["----------------------------------------",
                  "Only expired resources with a non-empty Owner tag are included.",
                  "Costs reflect available billing data for the period above, not live spending.",
                  "Resources without cost data are counted in the summary but excluded from ranking.",
                  "This tenancy-wide report is sent to all subscribers of the notification topic."])

    return "\n".join(lines)


def _publish_notification(config: Configuration, resources: list[dict[str, str]], dry_run: bool) -> None:
    topic_id = _env("OCI_MGMT_DASH_REPORT_NOTIFICATION_TOPIC_ID")
    if not topic_id:
        raise ValueError("Missing required setting: OCI_MGMT_DASH_REPORT_NOTIFICATION_TOPIC_ID")

    region = _env("OCI_MGMT_DASH_REPORT_NOTIFICATION_REGION")
    endpoint = _env("OCI_MGMT_DASH_REPORT_NOTIFICATION_ENDPOINT")
    title = _env("OCI_MGMT_DASH_REPORT_NOTIFICATION_TITLE", "OCI expired resources")
    try:
        max_items = int(_env("OCI_MGMT_DASH_REPORT_MAX_ITEMS", "25") or "25")
    except ValueError:
        max_items = 25
    costs, start, end = _load_report_costs(config)
    ranked = sorted(
        (item for item in resources if item.get("owner", "").strip() and item["identifier"] in costs),
        key=lambda item: (-costs[item["identifier"]][0], item["identifier"]),
    )
    _add_compartment_names(config, ranked[:min(25, max(1, max_items))])
    body = _build_message(resources, config.get_uri(), max_items, costs, start, end)

    if dry_run:
        logging.getLogger(__name__).info("Dry run notification title=%s body=\n%s", title, body)
        return

    cfg, signer = create_signer(
        config.get_auth_type(),
        profile=config.get_profile(),
        location=config.get_config_file(),
    )
    if region:
        cfg = dict(cfg)
        cfg["region"] = region

    client_kwargs = {"signer": signer}
    if endpoint:
        client_kwargs["service_endpoint"] = endpoint
    client = NotificationDataPlaneClient(cfg, **client_kwargs)
    response = client.publish_message(
        topic_id=topic_id,
        message_details=MessageDetails(title=title, body=body),
        message_type="RAW_TEXT",
    )
    logging.getLogger(__name__).info("Published expired resource report notification: %s", response.data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish expired OCI resource report to OCI Notifications.")
    parser.add_argument("--dry-run", action="store_true", help="Log the notification body without publishing.")
    args = parser.parse_args()

    logging.basicConfig(level=os.getenv("OCI_MGMT_DASH_LOG_LEVEL", "INFO").upper())
    logger = logging.getLogger(__name__)

    config = Configuration()
    resources = _find_expired_resources(config, logger)
    if not resources:
        logger.info("No expired resources found; no notification published.")
        return 0

    _publish_notification(config, resources, args.dry_run)
    logger.info("Expired resource notification job completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
