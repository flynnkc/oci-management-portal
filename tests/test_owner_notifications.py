from datetime import datetime, timezone
from decimal import Decimal
import hashlib
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from modules.reports.owner_routing import owner_email, group_by_owner
from modules.reports.notification_topics import OwnerTopics, MANAGER
from modules.reports import expired_resources_owner_notification as entry


@pytest.mark.parametrize('tag,email', [
    (' user@EXAMPLE.com ', 'user@example.com'),
    ('Default/User@example.com', 'user@example.com'),
    ('OCI_Management_Portal/user@example.com', 'user@example.com'),
    ('user+test@example.com', 'user+test@example.com'),
    ('', None), ('bad', None), ('a@b.com,b@c.com', None),
    ('name <a@b.com>', None), ('a/b/c@d.com', None),
    ('a\nb@c.com', None), ('a..b@c.com', None), ('a@-b.com', None),
])
def test_email_normalization(tag, email):
    assert owner_email(tag) == email


def test_grouping_normalizes_deduplicates_and_limits_domains():
    resources = [dict(identifier='1', owner='Default/A@example.com'),
                 dict(identifier='1', owner='a@example.com'),
                 dict(identifier='2', owner='a@example.com'),
                 dict(identifier='3', owner='b@external.com'),
                 dict(identifier='4', owner='')]
    groups, rejected = group_by_owner(resources, ['example.com'])
    assert list(groups) == ['a@example.com']
    assert [r['identifier'] for r in groups['a@example.com']] == ['1', '2']
    assert rejected == 2


def response(data, page=None):
    return NS(data=data, next_page=page)


def clients(email='a@example.com', exists=True, state='ACTIVE'):
    digest = hashlib.sha256(email.encode()).hexdigest()
    topic = NS(name='gitdash-expiry-a', topic_id='topic', lifecycle_state='ACTIVE',
               freeform_tags={'managed-by': MANAGER, 'owner-hash': digest})
    sub = NS(protocol='EMAIL', endpoint=email, lifecycle_state=state)
    control, data = Mock(), Mock()
    control.list_topics.return_value = response([topic] if exists else [])
    control.create_topic.return_value = response(topic)
    control.get_topic.return_value = response(topic)
    data.list_subscriptions.return_value = response([sub] if exists else [])
    return control, data, topic, sub


def test_readable_project_owner_name():
    control, data, _, _ = clients(exists=False)
    router = OwnerTopics(control, data, 'compartment', prefix='gitdash')
    assert router.name_for('test.1@oracle.com') == 'gitdash-test-1'
    assert router.name_for('test2@oracle.com') == 'gitdash-test2'
    assert router.name_for('User+test@example.com') == 'gitdash-user-test'


def test_legacy_topic_reused_and_published_without_new_subscription():
    control, data, topic, _ = clients()
    topic.name = 'gitdash-expiry-' + hashlib.sha256(b'a@example.com').hexdigest()[:32]
    router = OwnerTopics(control, data, 'compartment')
    assert router.ensure('a@example.com') == ('topic', 'active')
    router.publish('topic', 'a@example.com', 'title', 'body')
    control.create_topic.assert_not_called()
    data.create_subscription.assert_not_called()
    data.publish_message.assert_called_once()


def test_same_owner_name_different_email_is_blocked():
    control, data, _, _ = clients()
    router = OwnerTopics(control, data, 'compartment')
    with pytest.raises(ValueError, match='collision'):
        router.ensure('a@other.com')
    data.create_subscription.assert_not_called()
    data.publish_message.assert_not_called()


def test_readable_and_legacy_duplicates_are_blocked():
    from copy import deepcopy
    control, data, topic, _ = clients()
    legacy = deepcopy(topic)
    legacy.name = 'gitdash-expiry-' + hashlib.sha256(b'a@example.com').hexdigest()[:32]
    legacy.topic_id = 'legacy-topic'
    control.list_topics.return_value = response([topic, legacy])
    with pytest.raises(ValueError, match='Both readable and legacy'):
        OwnerTopics(control, data, 'compartment').ensure('a@example.com')
    control.create_topic.assert_not_called()


def test_new_owner_created_once_and_pending():
    control, data, topic, sub = clients(exists=False)
    router = OwnerTopics(control, data, 'compartment')
    assert router.ensure('a@example.com') == ('topic', 'pending-confirmation')
    assert control.create_topic.call_args.args[0].name == 'gitdash-expiry-a'
    assert data.create_subscription.call_args.args[0].endpoint == 'a@example.com'
    data.list_subscriptions.return_value = response([sub])
    control.list_topics.return_value = response([topic])
    assert router.ensure('a@example.com') == ('topic', 'active')
    control.create_topic.assert_called_once()
    data.create_subscription.assert_called_once()


def test_deleted_topic_recreated_with_new_token_and_new_ocid(monkeypatch):
    from modules.reports import notification_topics as module
    from copy import deepcopy
    monkeypatch.setattr(module.time, 'sleep', Mock())
    control, data, old, _ = clients()
    old.lifecycle_state = 'DELETING'
    new = deepcopy(old)
    new.topic_id, new.lifecycle_state = 'new-topic', 'ACTIVE'
    control.list_topics.side_effect = [response([old]), response([old]), response([])]
    control.create_topic.return_value = response(new)
    control.get_topic.return_value = response(new)
    data.list_subscriptions.return_value = response([])
    router = OwnerTopics(control, data, 'compartment')
    assert router.ensure('a@example.com') == ('new-topic', 'pending-confirmation')
    assert data.create_subscription.call_args.args[0].topic_id == 'new-topic'
    first_token = control.create_topic.call_args.kwargs['opc_retry_token']
    control.list_topics.side_effect = None
    control.list_topics.return_value = response([])
    router.ensure('a@example.com')
    assert control.create_topic.call_args.kwargs['opc_retry_token'] != first_token


def test_subscription_propagation_retries_same_token(monkeypatch):
    from modules.reports import notification_topics as module
    from oci.exceptions import ServiceError
    monkeypatch.setattr(module.time, 'sleep', Mock())
    control, data, _, _ = clients(exists=False)
    data.create_subscription.side_effect = [ServiceError(404, 'NotAuthorizedOrNotFound', {}, 'not found'), response(None)]
    assert OwnerTopics(control, data, 'compartment').ensure('a@example.com')[1] == 'pending-confirmation'
    calls = data.create_subscription.call_args_list
    assert len(calls) == 2
    assert calls[0].kwargs['opc_retry_token'] == calls[1].kwargs['opc_retry_token']


def test_persistent_404_is_bounded(monkeypatch):
    from modules.reports import notification_topics as module
    from oci.exceptions import ServiceError
    monkeypatch.setattr(module.time, 'sleep', Mock())
    control, data, _, _ = clients(exists=False)
    data.create_subscription.side_effect = ServiceError(404, 'NotAuthorizedOrNotFound', {}, 'not found')
    with pytest.raises(ServiceError):
        OwnerTopics(control, data, 'compartment').ensure('a@example.com')
    assert data.create_subscription.call_count == module.ATTEMPTS
    control.create_topic.assert_called_once()


def test_waits_for_active_before_subscription(monkeypatch):
    from modules.reports import notification_topics as module
    from copy import deepcopy
    monkeypatch.setattr(module.time, 'sleep', Mock())
    control, data, topic, _ = clients(exists=False)
    creating = deepcopy(topic)
    creating.lifecycle_state = 'CREATING'
    control.get_topic.side_effect = [response(creating), response(topic)]
    assert OwnerTopics(control, data, 'compartment').ensure('a@example.com')[1] == 'pending-confirmation'
    assert control.get_topic.call_count == 2
    data.create_subscription.assert_called_once()


def test_dry_run_has_no_writes():
    control, data, _, _ = clients(exists=False)
    assert OwnerTopics(control, data, 'compartment').ensure('a@example.com', True)[1].startswith('would-create')
    control.create_topic.assert_not_called()
    data.create_subscription.assert_not_called()
    data.publish_message.assert_not_called()


def test_pending_and_unsubscribed_are_not_recreated():
    control, data, _, _ = clients(state='PENDING')
    router = OwnerTopics(control, data, 'compartment')
    assert router.ensure('a@example.com')[1] == 'pending-confirmation'
    data.list_subscriptions.return_value = response([])
    assert router.ensure('a@example.com')[1] == 'missing-subscription-review-required'
    data.create_subscription.assert_not_called()


def test_unexpected_recipient_on_second_page_blocks_publish():
    control, data, _, sub = clients()
    data.list_subscriptions.side_effect = [response([sub], 'next'),
        response([NS(protocol='EMAIL', endpoint='other@example.com', lifecycle_state='ACTIVE')])]
    router = OwnerTopics(control, data, 'compartment')
    with pytest.raises(ValueError, match='exactly one'):
        router.publish('topic', 'a@example.com', 'title', 'private body')
    data.publish_message.assert_not_called()
    assert data.list_subscriptions.call_args.args == ('compartment',)
    assert data.list_subscriptions.call_args.kwargs == {'topic_id': 'topic', 'page': 'next'}


def test_unmanaged_topic_and_wrong_endpoint_blocked():
    control, data, topic, sub = clients()
    router = OwnerTopics(control, data, 'compartment')
    topic.freeform_tags = {}
    with pytest.raises(ValueError, match='collision'):
        router.ensure('a@example.com')
    _, _, good, _ = clients()
    topic.freeform_tags = good.freeform_tags
    sub.endpoint = 'other@example.com'
    with pytest.raises(ValueError, match='unexpected recipient'):
        router.ensure('a@example.com')


def test_owner_entrypoint_isolates_reports_and_continues_on_failure(monkeypatch):
    monkeypatch.setenv('OCI_MGMT_DASH_REPORT_OWNER_COMPARTMENT_ID', 'compartment')
    monkeypatch.setenv('OCI_MGMT_DASH_REPORT_NOTIFICATION_REGION', 'us-phoenix-1')
    monkeypatch.delenv('OCI_MGMT_DASH_REPORT_OWNER_ALLOWED_DOMAINS', raising=False)
    resources = [dict(identifier=str(i), owner=email, display_name='resource-' + str(i),
                      resource_type='Instance', compartment_name='Production')
                 for i, email in enumerate(['a@example.com', 'b@example.com'])]
    monkeypatch.setattr(entry.shared, '_find_expired_resources', lambda *a: resources)
    monkeypatch.setattr(entry, 'create_signer', lambda *a, **k: ({}, None))
    monkeypatch.setattr(entry, 'NotificationControlPlaneClient', Mock())
    monkeypatch.setattr(entry, 'NotificationDataPlaneClient', Mock())
    router = Mock()
    router.ensure.side_effect = [('topic-a', 'active'), ('topic-b', 'active')]
    router.publish.side_effect = [RuntimeError('first owner failed'), None]
    monkeypatch.setattr(entry, 'OwnerTopics', Mock(return_value=router))
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    end = datetime(2026, 8, 31, tzinfo=timezone.utc)
    monkeypatch.setattr(entry.shared, '_load_report_costs', lambda *a: (
        {'0': (Decimal(10), 'USD'), '1': (Decimal(20), 'USD')}, start, end))
    monkeypatch.setattr(entry.shared, '_add_compartment_names', Mock())
    config = Mock()
    config.get_uri.return_value = 'http://132.226.85.232'
    assert entry.run(config) == 1
    assert router.publish.call_count == 2
    first = router.publish.call_args_list[0].args[3]
    second = router.publish.call_args_list[1].args[3]
    assert 'resource-0' in first and 'resource-1' not in first
    assert 'resource-1' in second and 'resource-0' not in second
    assert 'Owner summary: a@example.com' in first
    assert 'Total Expired resources: 1' in first
    assert 'Tenancy-wide' not in first
