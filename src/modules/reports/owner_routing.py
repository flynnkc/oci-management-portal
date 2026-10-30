"""Conservative Owner-tag email normalization and grouping for reports."""
from collections import defaultdict
import re


def owner_email(value: str) -> str | None:
    value = (value or "").strip()
    if "/" in value:
        parts = value.split("/")
        if len(parts) != 2 or not re.fullmatch(r"[A-Za-z0-9_. -]+", parts[0]):
            return None
        value = parts[1].strip()
    if len(value) > 254 or value.count("@") != 1:
        return None
    local, domain = value.rsplit("@", 1)
    if (not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+=?^_`{|}~-]{1,64}", local)
            or local.startswith(".") or local.endswith(".") or ".." in local):
        return None
    labels = domain.split(".")
    if len(labels) < 2 or any(not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", p) for p in labels):
        return None
    # Corporate identity matching is case insensitive; keep + aliases distinct.
    return value.lower()


def group_by_owner(resources, allowed_domains=()):
    groups = defaultdict(list)
    rejected = 0
    seen = set()
    domains = {d.strip().lower() for d in allowed_domains if d.strip()}
    for resource in resources:
        email = owner_email(resource.get("owner", ""))
        if not email or (domains and email.rsplit("@", 1)[1] not in domains):
            rejected += 1
            continue
        identifier = resource.get("identifier")
        if not identifier or identifier in seen:
            continue
        seen.add(identifier)
        groups[email].append(resource)
    return dict(groups), rejected
