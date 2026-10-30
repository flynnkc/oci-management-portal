"""Owner-only reports; the existing manager report remains a separate entry point."""
import argparse
import logging
import os

from oci.ons import NotificationControlPlaneClient, NotificationDataPlaneClient

from ..config import Configuration
from ..signer import create_signer
from . import expired_resources_notification as shared
from .owner_routing import group_by_owner
from .notification_topics import OwnerTopics


def run(config, dry_run=False):
    logger = logging.getLogger(__name__)
    compartment = shared._env("OCI_MGMT_DASH_REPORT_OWNER_COMPARTMENT_ID")
    region = shared._env("OCI_MGMT_DASH_REPORT_NOTIFICATION_REGION")
    if not compartment or not region:
        raise ValueError("Owner mode requires owner compartmentId and notification.region")
    groups, rejected = group_by_owner(shared._find_expired_resources(config, logger),
        shared._split_csv(shared._env("OCI_MGMT_DASH_REPORT_OWNER_ALLOWED_DOMAINS")))
    logger.info("Owner groups=%d rejected owner tags=%d", len(groups), rejected)
    if not groups:
        return 0
    cfg, signer = create_signer(config.get_auth_type(), profile=config.get_profile(),
                                location=config.get_config_file())
    cfg = dict(cfg, region=region)
    topics = OwnerTopics(NotificationControlPlaneClient(cfg, signer=signer),
                        NotificationDataPlaneClient(cfg, signer=signer), compartment,
                        shared._env("OCI_MGMT_DASH_REPORT_OWNER_TOPIC_PREFIX", "gitdash-expiry"))
    costs, start, end = shared._load_report_costs(config)
    try:
        limit = min(25, max(1, int(shared._env("OCI_MGMT_DASH_REPORT_MAX_ITEMS", "25"))))
    except ValueError:
        limit = 25
    failures = 0
    for email, resources in sorted(groups.items()):
        try:
            topic_id, status = topics.ensure(email, dry_run=dry_run)
            logger.info("Owner=%s resources=%d topic=%s status=%s", email, len(resources),
                        topics.name_for(email), status)
            if not dry_run and status != "active":
                if status not in ("pending-confirmation", "topic-inactive"):
                    failures += 1
                continue
            ranked = sorted((r for r in resources if r["identifier"] in costs),
                            key=lambda r: (-costs[r["identifier"]][0], r["identifier"]))
            shared._add_compartment_names(config, ranked[:limit])
            body = shared._build_message(resources, config.get_uri(), limit, costs, start, end)
            body = body.replace("Tenancy-wide summary", f"Owner summary: {email}", 1)
            body = body.replace("This tenancy-wide report is sent to all subscribers of the notification topic.",
                                "This report contains only resources assigned to your owner email.")
            if dry_run:
                logger.info("DRY RUN (no writes or emails):\n%s", body)
            else:
                topics.publish(topic_id, email,
                    shared._env("OCI_MGMT_DASH_REPORT_NOTIFICATION_TITLE", "OCI expired resources"), body)
                logger.info("Published owner report topic=%s", topic_id)
        except Exception:
            failures += 1
            logger.exception("Owner report failed for %s; continuing other owners", email)
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description="Send expired resource reports to dedicated owner topics")
    parser.add_argument("--dry-run", action="store_true", help="Read-only preview: no topics, subscriptions or messages created")
    args = parser.parse_args()
    logging.basicConfig(level=os.getenv("OCI_MGMT_DASH_LOG_LEVEL", "INFO").upper())
    return run(Configuration(), args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
