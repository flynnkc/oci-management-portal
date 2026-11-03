"""Exercise authentication and HTML boundaries without making OCI calls."""

import importlib.util
import sys
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from modules.actions.result import Result


@pytest.fixture
def web(monkeypatch, tmp_path):
    for key, value in {
        'IDM_ENDPOINT': 'https://identity.example.com',
        'CLIENT_ID': 'test-client',
        'CLIENT_SECRET': 'test-secret',
        'CLEANUP_CMP': 'ocid1.compartment.oc1..cleanup',
        'TAG_NAMESPACE': 'Usage',
        'TAG_KEY': 'Owner',
        'FILTER_KEY': 'Expires',
        'SESSION_BACKEND': 'filesystem',
    }.items():
        monkeypatch.setenv(f'OCI_MGMT_DASH_{key}', value)
    monkeypatch.delenv('OCI_MGMT_DASH_SESSION_COOKIE_SECURE', raising=False)
    monkeypatch.delenv('OCI_MGMT_DASH_LOG_FILE', raising=False)
    search = SimpleNamespace(
        home_region='us-ashburn-1',
        region_names=['us-ashburn-1'],
        validate_resource=Mock(return_value=True),
        get_resource_by_id=Mock(),
    )
    deleter = SimpleNamespace(delete=Mock(return_value=Result(200, metadata={'method': 'force'})))
    chaser = SimpleNamespace(get_work_request=Mock(return_value='SUCCEEDED'))
    ctx = SimpleNamespace(
        search=search,
        oauth=SimpleNamespace(
            login_redirect_uri=Mock(return_value='https://identity.example.com/authorize'),
            retrieve_token=Mock(return_value={
                'id_claims': {}, 'access_token': 'test-token', 'expires_in': 3600,
            }),
            build_user_context=Mock(return_value={'user': 'owner@example.com'}),
        ),
        clear_user_token_exchange_cache=Mock(),
        get_oci_services=Mock(return_value={
            'search': search, 'deleter': deleter, 'request_chaser': chaser,
        }),
        cost_service=SimpleNamespace(get_current_costs=Mock(return_value={})),
        cfg={'tenancy': 'test-tenancy'},
    )
    monkeypatch.setattr('modules.handlers.initialize_service_context', lambda *args: ctx)
    source = Path(__file__).resolve().parents[1] / 'src' / 'wsgi.py'
    # Isolate the real filesystem session backend under pytest's temporary dir.
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location('security_test_wsgi', source)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    module.app.config['TESTING'] = True
    return module, ctx


def test_login_rotates_session_and_invalidates_old_id(web):
    module, _ = web
    app = module.app
    client = app.test_client()
    assert client.get('/login', base_url='https://localhost').status_code == 302
    old_sid = client.get_cookie('omid').value
    with client.session_transaction() as pending:
        state = pending['state']

    response = client.get('/callback', base_url='https://localhost', query_string={
        'state': state, 'code': 'test-code',
    })
    assert response.status_code == 302
    assert client.get_cookie('omid').value != old_sid
    with client.session_transaction() as authenticated:
        assert authenticated['user'] == 'owner@example.com'
        assert authenticated['oauth_tokens']['access_token'] == 'test-token'
        assert 'state' not in authenticated
        assert 'nonce' not in authenticated

    replay = app.test_client()
    replay.set_cookie('omid', old_sid)
    assert replay.post('/costs/batch', base_url='https://localhost', json={}).status_code == 401
    assert client.post('/costs/batch', base_url='https://localhost', json={}).status_code == 200


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


@pytest.mark.parametrize('path', ['poll', 'force'])
@pytest.mark.parametrize('identifier', [
    'ocid1.instance.oc1.iad.example',
    '"></template><img src=x onerror=alert(1)>',
    '" onmouseover=alert(1) data-injected="yes',
])
def test_delete_fragments_keep_identifiers_inside_escaped_attributes(web, path, identifier):
    module, ctx = web
    client = module.app.test_client()
    with client.session_transaction() as authenticated:
        authenticated['user'] = 'owner@example.com'
        authenticated['csrf_tokens'] = {'test-csrf': None}
    if path == 'poll':
        response = client.get('/r', base_url='https://localhost', query_string={
            'id': 'test-work-request', 'action': 'DELETE', 'identifier': identifier,
        })
    else:
        ctx.search.get_resource_by_id.return_value = {'identifier': identifier}
        response = client.delete('/delete', base_url='https://localhost', data={
            'identifier': identifier, 'csrf_token': 'test-csrf',
        })
        services = ctx.get_oci_services.return_value
        services['deleter'].delete.assert_called_once()

    assert response.status_code == 200
    elements = Elements(response.get_data(as_text=True)).elements
    templates = [attrs for tag, attrs in elements if tag == 'template']
    assert templates == [{'hx-swap-oob': 'delete', 'id': 'card-' + identifier.replace('.', '-')}]
    assert not any(tag in ('img', 'script') for tag, _ in elements)
    assert not any(name.startswith('on') for _, attrs in elements for name in attrs)


@pytest.mark.parametrize('setting,secure', [(None, True), ('true', True), ('false', False)])
def test_cookie_secure_default_and_local_http_override(web, monkeypatch, setting, secure):
    module, _ = web
    if setting is not None:
        monkeypatch.setenv('OCI_MGMT_DASH_SESSION_COOKIE_SECURE', setting)
    app = module.create_app()
    assert app.config['SESSION_COOKIE_SECURE'] is secure
    response = app.test_client().get('/login', base_url='https://localhost' if secure else 'http://localhost')
    cookie = response.headers['Set-Cookie']
    assert ('; Secure' in cookie) is secure
    assert '; HttpOnly' in cookie
    assert '; SameSite=Lax' in cookie
