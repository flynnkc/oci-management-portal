"""Application-owned ONS topics, each restricted to one owner email."""
import hashlib
import re
import logging
import time
from uuid import uuid4

from oci.exceptions import ServiceError
from oci.retry import DEFAULT_RETRY_STRATEGY

from oci.ons.models import CreateTopicDetails, CreateSubscriptionDetails, MessageDetails

MANAGER = "gitdash-owner-report-v1"
logger = logging.getLogger(__name__)
ATTEMPTS = 7
RETRY_SECONDS = 10


class OwnerTopics:
    def __init__(self, control, data, compartment_id, prefix="gitdash-expiry"):
        if not compartment_id:
            raise ValueError("Owner notification compartmentId is required")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", prefix):
            raise ValueError("topicPrefix must be 1-40 letters, digits, underscores or hyphens, starting with a letter")
        self.control, self.data = control, data
        self.compartment_id, self.prefix = compartment_id, prefix
        self.topics = {}
        self._refresh_topics()

    def _refresh_topics(self):
        topics = {}
        page = None
        while True:
            result = self.control.list_topics(compartment_id=self.compartment_id, page=page)
            for topic in result.data:
                if topic.lifecycle_state == "DELETED":
                    continue
                if topic.name in topics:
                    raise ValueError("Duplicate topic names; resolve before sending owner reports")
                topics[topic.name] = topic
            page = result.next_page
            if not page:
                break
        self.topics = topics

    def _check_owner(self, topic, email):
        tags = topic.freeform_tags or {}
        if (topic.name not in (self.name_for(email), self._legacy_name_for(email)) or tags.get("managed-by") != MANAGER
                or tags.get("owner-hash") != hashlib.sha256(email.encode()).hexdigest()):
            raise ValueError("Topic name collision or owner mismatch; publishing blocked")

    def _wait_active(self, topic, email):
        for attempt in range(ATTEMPTS):
            try:
                fresh = self.control.get_topic(topic.topic_id).data
                self._check_owner(fresh, email)
                if fresh.lifecycle_state == "ACTIVE":
                    return fresh
                if fresh.lifecycle_state not in ("CREATING", "UPDATING"):
                    raise ValueError(f"Topic {topic.topic_id} has state {fresh.lifecycle_state}; retry on next run")
            except ServiceError as exc:
                if exc.status != 404 or attempt == ATTEMPTS - 1:
                    raise
            if attempt < ATTEMPTS - 1:
                logger.info("Waiting for topic ACTIVE: topic=%s attempt=%d/%d", topic.topic_id, attempt + 1, ATTEMPTS)
                time.sleep(RETRY_SECONDS)
        raise TimeoutError(f"Topic {topic.topic_id} did not become ACTIVE; check OCI state and permissions")

    def _retry_propagation(self, operation, topic_id):
        for attempt in range(ATTEMPTS):
            try:
                return operation()
            except ServiceError as exc:
                if exc.status not in (404, 429, 500, 502, 503, 504) or attempt == ATTEMPTS - 1:
                    raise
                logger.warning("ONS not ready: topic=%s status=%s attempt=%d/%d; retrying in %ds",
                               topic_id, exc.status, attempt + 1, ATTEMPTS, RETRY_SECONDS)
                time.sleep(RETRY_SECONDS)

    def name_for(self, email):
        owner = re.sub(r"[^a-z0-9_-]+", "-", email.split("@", 1)[0].lower()).strip("-_")
        return f"{self.prefix}-{owner or 'owner'}"

    def _legacy_name_for(self, email):
        return f"{self.prefix}-{hashlib.sha256(email.encode()).hexdigest()[:32]}"

    def _find_topic(self, email):
        current = self.topics.get(self.name_for(email))
        legacy = self.topics.get(self._legacy_name_for(email))
        if current is not None and legacy is not None and current.topic_id != legacy.topic_id:
            raise ValueError("Both readable and legacy owner topics exist; resolve before sending")
        topic = current if current is not None else legacy
        if topic is not None:
            self._check_owner(topic, email)
        return topic

    def _subscriptions(self, topic_id):
        subscriptions, page = [], None
        while True:
            # The deployed ONS endpoint requires a compartment even with topic_id.
            # Keep managed subscriptions in this compartment; restrict moves via IAM.
            result = self.data.list_subscriptions(
                self.compartment_id, topic_id=topic_id, page=page)
            subscriptions.extend(result.data)
            page = result.next_page
            if not page:
                return subscriptions

    def _status(self, topic, email):
        subscriptions = self._subscriptions(topic.topic_id)
        if not subscriptions:
            return "missing-subscription-review-required"
        if len(subscriptions) != 1:
            raise ValueError("Owner topic must contain exactly one subscription")
        sub = subscriptions[0]
        if sub.protocol != "EMAIL" or sub.endpoint.strip().lower() != email:
            raise ValueError("Owner topic contains an unexpected recipient; publishing blocked")
        if sub.lifecycle_state == "ACTIVE":
            return "active"
        if sub.lifecycle_state == "PENDING":
            return "pending-confirmation"
        return "subscription-inactive"

    def ensure(self, email, dry_run=False):
        name = self.name_for(email)
        # A previous run or operator may have deleted/recreated this topic.
        self._refresh_topics()
        topic = self._find_topic(email)
        digest = hashlib.sha256(email.encode()).hexdigest()
        if topic is not None:
            self._check_owner(topic, email)
            if topic.lifecycle_state == "DELETING" and not dry_run:
                for attempt in range(ATTEMPTS):
                    self._refresh_topics()
                    topic = self._find_topic(email)
                    if topic is None or topic.lifecycle_state != "DELETING":
                        break
                    if attempt == ATTEMPTS - 1:
                        raise TimeoutError(f"Topic {topic.topic_id} is still deleting; retry next scheduled run")
                    logger.info("Waiting for topic deletion: topic=%s", topic.topic_id)
                    time.sleep(RETRY_SECONDS)
        if topic is None:
            if dry_run:
                return None, "would-create-topic-and-subscription"
            logger.info("Creating owner topic: name=%s compartment=%s", name, self.compartment_id)
            topic = self.control.create_topic(CreateTopicDetails(
                name=name, compartment_id=self.compartment_id,
                description="Dedicated owner expiry report. Do not add other recipients.",
                freeform_tags={"managed-by": MANAGER, "owner-hash": digest},
            ), opc_retry_token=str(uuid4()), retry_strategy=DEFAULT_RETRY_STRATEGY).data
            self.topics[name] = topic
            logger.info("Created topic: name=%s topic_id=%s", name, topic.topic_id)
            topic = self._wait_active(topic, email)
            # Only the creation run provisions the initial subscription. An existing
            # topic without a subscription is never silently re-subscribed: it may
            # represent an unsubscribe or an uncertain prior creation result.
            if self._retry_propagation(lambda: self._subscriptions(topic.topic_id), topic.topic_id):
                raise ValueError("New topic unexpectedly contains subscriptions")
            details = CreateSubscriptionDetails(
                compartment_id=self.compartment_id, topic_id=topic.topic_id,
                protocol="EMAIL", endpoint=email,
            )
            token = str(uuid4())  # Reuse only within this subscription creation attempt.
            self._retry_propagation(lambda: self.data.create_subscription(
                details, opc_retry_token=token), topic.topic_id)
            logger.info("Created owner EMAIL subscription: topic=%s; awaiting confirmation", topic.topic_id)
            return topic.topic_id, "pending-confirmation"
        tags = topic.freeform_tags or {}
        if tags.get("managed-by") != MANAGER or tags.get("owner-hash") != digest:
            raise ValueError("Topic name collision or owner mismatch; publishing blocked")
        if topic.lifecycle_state in ("CREATING", "UPDATING") and not dry_run:
            topic = self._wait_active(topic, email)
        if topic.lifecycle_state != "ACTIVE":
            return topic.topic_id, "topic-inactive"
        return topic.topic_id, self._status(topic, email)

    def publish(self, topic_id, email, title, body):
        # Recheck immediately before publication. IAM must prevent unrelated users
        # from adding subscribers; ONS cannot atomically check and publish.
        topic = self.control.get_topic(topic_id).data
        self._check_owner(topic, email)
        if topic.lifecycle_state != "ACTIVE":
            raise ValueError("Topic ownership/state changed; publishing blocked")
        if self._status(topic, email) != "active":
            raise ValueError("Owner subscription is no longer active")
        if len(body.encode("utf-8")) > 60 * 1024:
            raise ValueError("Owner report exceeds safe ONS payload size")
        return self.data.publish_message(topic_id=topic_id,
            message_details=MessageDetails(title=title, body=body), message_type="RAW_TEXT")
