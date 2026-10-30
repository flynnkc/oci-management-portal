from datetime import datetime, timezone
from decimal import Decimal
import logging
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from modules.reports import expired_resources_notification as report


def config():
    return Mock(**{
        'get_filter.return_value': NS(namespace='Management', key='Expires'),
        'get_mgmt_tag.return_value': NS(namespace='Management', key='Owner'),
        'get_cleanup_compartment.return_value': 'cleanup',
    })


def response(items, page=None):
    return NS(data=NS(items=items), next_page=page)


def test_unique_expired_resources_across_regions_and_pages(monkeypatch):
    def item(ocid, expires, owner='user@example.com'):
        return NS(identifier=ocid, defined_tags={'Management': {'Expires': expires, 'Owner': owner}},
                  display_name=ocid)
    client = Mock()
    client.search_resources.side_effect = [
        response([item('a', '2020-01-01'), item('bad', 'invalid'),
                  item('empty', '2020-01-01', ''), item('blank', '2020-01-01', '  '),
                  NS(identifier='missing', defined_tags={'Management': {'Expires': '2020-01-01'}})], 'page2'),
        response([item('b', '2020-01-01'), item('future', '2999-01-01')]),
        response([item('a', '2020-01-01'), item('b', '2020-01-01')]),
    ]
    monkeypatch.setattr(report, 'create_signer', lambda *a, **k: ({'tenancy': 'tenant'}, None))
    monkeypatch.setattr(report, '_configured_regions', lambda *a: ['r1', 'r2'])
    monkeypatch.setattr(report.resource_search, 'ResourceSearchClient', lambda *a, **k: client)
    resources = report._find_expired_resources(config(), logging.getLogger('test'))
    assert [r['identifier'] for r in resources] == ['a', 'b']
    assert client.search_resources.call_args_list[1].kwargs['page'] == 'page2'


def test_cost_pages_are_aggregated_in_home_region(monkeypatch):
    monkeypatch.setattr(report, 'create_signer', lambda *a, **k: ({'tenancy': 'tenant'}, None))
    identity = Mock()
    identity.list_region_subscriptions.return_value.data = [NS(region_name='home', is_home_region=True)]
    monkeypatch.setattr(report, 'IdentityClient', lambda *a, **k: identity)
    client = Mock()
    client.request_summarized_usages.side_effect = [
        response([NS(resource_id='a', computed_amount=2, currency='USD')], 'next'),
        response([NS(resource_id='a', computed_amount=3, currency='USD')]),
    ]
    factory = Mock(return_value=client)
    monkeypatch.setattr(report.usage_api, 'UsageapiClient', factory)
    costs, start, end = report._load_report_costs(config())
    assert costs['a'] == (Decimal(5), 'USD')
    assert (end-start).days == 30
    assert factory.call_args.args[0]['region'] == 'home'
    assert client.request_summarized_usages.call_args_list[1].kwargs['page'] == 'next'


def test_message_top_25_cost_order_owner_and_missing_cost():
    resources = [dict(identifier=str(i), display_name=f'resource-{i}', resource_type='Instance',
                      region='phx', owner=f'owner-{i}', expiry='2020-01-01') for i in range(30)]
    costs = {str(i): (Decimal(i), 'USD') for i in range(29)}
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    body = report._build_message(resources, 'https://portal.example.com', 100, costs, start,
                                 datetime(2026, 8, 31, tzinfo=timezone.utc))
    assert 'Total Expired resources: 30' in body
    assert 'Resources with cost data:' not in body
    assert 'Resources without cost data:' not in body
    assert 'Portal: http://portal.example.com' in body
    rows = [line for line in body.splitlines() if ' | ' in line and line.split('|')[0].strip().isdigit()]
    assert len(rows) == 25
    assert 'USD 28.00' in rows[0] and 'USD 4.00' in rows[-1]
    assert [cell.strip() for cell in rows[0].split('|')] == ['1', 'resource-28', 'Instance', 'Not available', 'owner-28', 'USD 28.00']
    assert [cell.strip() for cell in rows[-1].split('|')][:2] == ['25', 'resource-4']
    assert 'phx' not in body and 'OCID=' not in body
    assert '2020-01-01' not in body
    assert 'Monthly' not in body


def test_message_missing_name_owner_and_cost():
    resources = [dict(identifier='ocid-secret', display_name='', owner='')]
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    end = datetime(2026, 8, 31, tzinfo=timezone.utc)
    body = report._build_message(resources, '', 25, {'ocid-secret': (Decimal('1234.56'), 'USD')}, start, end)
    assert 'Total Expired resources: 0' in body
    assert 'Owner: Unassigned' not in body
    assert 'USD 1,234.56' not in body
    assert 'ocid-secret' not in body
    body = report._build_message(resources, '', 25, {}, start, end)
    assert 'No resource-level cost data available' in body


def test_compartment_names_cached_and_permission_fallback(monkeypatch):
    monkeypatch.setattr(report, 'create_signer', lambda *a, **k: ({}, None))
    client = Mock()
    client.get_compartment.side_effect = [NS(data=NS(name='Production')),
        report.ServiceError(404, 'NotAuthorizedOrNotFound', {}, 'unavailable')]
    monkeypatch.setattr(report, 'IdentityClient', lambda *a, **k: client)
    resources = [dict(compartment_id='c1'), dict(compartment_id='c1'), dict(compartment_id='c2')]
    report._add_compartment_names(config(), resources)
    assert resources[0]['compartment_name'] == resources[1]['compartment_name'] == 'Production'
    assert resources[2]['compartment_name'] == 'Name unavailable (c2)'
    assert client.get_compartment.call_count == 2


def test_cost_failure_does_not_publish(monkeypatch):
    monkeypatch.setenv('OCI_MGMT_DASH_REPORT_NOTIFICATION_TOPIC_ID', 'topic')
    monkeypatch.setattr(report, '_load_report_costs', Mock(side_effect=RuntimeError('denied')))
    publish_client = Mock()
    monkeypatch.setattr(report, 'NotificationDataPlaneClient', publish_client)
    with pytest.raises(RuntimeError, match='denied'):
        report._publish_notification(config(), [], False)
    publish_client.assert_not_called()
