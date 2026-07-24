# tests/test_chatwoot_integration.py
"""Integration tests for ChatwootHandler.

PocketBase dev is hit for real; all Chatwoot HTTP calls are intercepted by mock.
_process_all() is called directly (synchronous) to avoid threading races.
"""

import json
import os
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest

from app.handlers.chatwoot.handler import ChatwootHandler
from app.handlers.resolver import DefaultVariableResolver
from app.schemas import MessengerCampaignMeta, MessengerPayload, MessengerRecipient

_TEST_INSTANCE_ID = os.getenv('TEST_CHATWOOT_INSTANCE_ID', '87v79w2os56q298')

# The happy-path tests below require a fully PROVISIONED Chatwoot instance in
# PocketBase (channel config + service secret for _TEST_INSTANCE_ID). That graph
# isn't part of the core monk-api schema (pb_schema.json), so they're opt-in via
# TEST_CHATWOOT_INSTANCE_ID — matching the sibling tests in test_chatwoot_handler.py.
# The skip-path and endpoint tests below need no provisioning and always run.
_requires_provisioned_instance = pytest.mark.skipif(
    not os.getenv('TEST_CHATWOOT_INSTANCE_ID'),
    reason='requires a provisioned Chatwoot instance (channel config + secret) in PocketBase',
)

# --------------------------------------------------------------------------- #
# Template body — instancia.* fields use :<default> so tests work without
# an `instancias` PocketBase record (handler returns {} on error).
# --------------------------------------------------------------------------- #
TEMPLATE_BODY = json.dumps({
    'content': 'Oi, {{1}}! Fatura de {{2}} da {{3}}.',
    'message_type': 'outgoing',
    'private': False,
    'content_type': 'text',
    'template_params': {
        'name': 'cobranca_v2',
        'language': 'pt_BR',
        'category': 'UTILITY',
        'processed_params': {
            'body': {
                '1': 'lead.name:amigo',
                '2': 'campanha.subject:assunto',
                '3': 'instancia.razao_social:Empresa',
            },
            'buttons': [],
        },
    },
})

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def handler():
    return ChatwootHandler(resolver=DefaultVariableResolver())


@pytest.fixture
def recipient():
    return MessengerRecipient(
        uuid='r-integration-001',
        email='joao@example.com',
        name='João Integration',
        attribs={'phone': '+5511999999999'},
        status='enabled',
    )


@pytest.fixture
def integration_payload(recipient):
    return MessengerPayload(
        subject='Fatura de integração',
        body=TEMPLATE_BODY,
        content_type='plain',
        campaign=MessengerCampaignMeta(
            uuid='camp-integration-001',
            name='Cobrança Integration',
            tags=['cobranca', f'instance:{_TEST_INSTANCE_ID}'],
        ),
        recipients=[recipient],
    )


@pytest.fixture
def chatwoot_session():
    """Mock requests.Session that simulates a successful Chatwoot API flow, keyed by URL so it
    tolerates the label calls (ensure account labels + assign to conversation) in any order."""
    session = MagicMock()

    search_resp = MagicMock(ok=True)
    search_resp.json.return_value = {'payload': []}
    session.get.return_value = search_resp

    def _post(url, *args, **kwargs):
        resp = MagicMock(ok=True)
        if url.endswith('/contacts'):
            resp.json.return_value = {'id': 42}
        elif url.endswith('/conversations'):
            resp.json.return_value = {'id': 99}
        else:  # /labels (ensure + assign) and /messages
            resp.json.return_value = {}
        return resp

    session.post.side_effect = _post
    return session


# --------------------------------------------------------------------------- #
# Full flow — reads real PocketBase config
# --------------------------------------------------------------------------- #


@_requires_provisioned_instance
def test_full_flow_reads_pb_config(handler, integration_payload, chatwoot_session):
    """_process_all fetches the real mxf config from PocketBase and sends 3 Chatwoot calls."""
    with patch('app.handlers.chatwoot.handler.requests.Session', return_value=chatwoot_session):
        handler._process_all(integration_payload)

    # the full flow ran: a contact search + a template message POST (a template-fetch GET also happens)
    assert any(c.args[0].endswith('/contacts/search') for c in chatwoot_session.get.call_args_list)
    assert any(c.args[0].endswith('/messages') for c in chatwoot_session.post.call_args_list)


@_requires_provisioned_instance
def test_resolved_variables_in_chatwoot_payload(handler, integration_payload, chatwoot_session):
    """processed_params in the message body must contain resolved variable values."""
    with patch('app.handlers.chatwoot.handler.requests.Session', return_value=chatwoot_session):
        handler._process_all(integration_payload)

    # find the message POST by URL (label calls now interleave) and inspect its json body
    msg_call = next(c for c in chatwoot_session.post.call_args_list if c.args[0].endswith('/messages'))
    processed = msg_call.kwargs['json']['template_params']['processed_params']

    assert processed['1'] == 'João Integration'  # lead.name
    assert processed['2'] == 'Fatura de integração'  # campanha.subject
    # instancia.razao_social falls back to default since `instancias` collection is absent
    assert processed['3'] == 'Empresa'


@_requires_provisioned_instance
def test_instancia_fallback_default_used(handler, chatwoot_session):
    """When instancias has no record, template defaults are applied and recipient is not skipped."""
    payload = MessengerPayload(
        subject='Test fallback',
        body=TEMPLATE_BODY,
        content_type='plain',
        campaign=MessengerCampaignMeta(uuid='c-fb', name='Fallback', tags=[f'instance:{_TEST_INSTANCE_ID}']),
        recipients=[
            MessengerRecipient(
                uuid='r-fb', email='fb@x.com', name='Fallback User', attribs={'phone': '+5511000000000'}, status='enabled'
            )
        ],
    )

    with patch('app.handlers.chatwoot.handler.requests.Session', return_value=chatwoot_session):
        handler._process_all(payload)

    # recipient was NOT skipped — a template message was sent
    assert any(c.args[0].endswith('/messages') for c in chatwoot_session.post.call_args_list)


# --------------------------------------------------------------------------- #
# Skip conditions — real PB config, selective mocking
# --------------------------------------------------------------------------- #


def test_recipient_missing_phone_skipped(handler, chatwoot_session):
    """A recipient without attribs.phone must be skipped — zero Chatwoot calls."""
    payload = MessengerPayload(
        subject='No phone',
        body=TEMPLATE_BODY,
        content_type='plain',
        campaign=MessengerCampaignMeta(uuid='c-np', name='No Phone', tags=['instance:87v79w2os56q298']),
        recipients=[MessengerRecipient(uuid='r-np', email='np@x.com', name='No Phone', attribs={}, status='enabled')],
    )

    with patch('app.handlers.chatwoot.handler.requests.Session', return_value=chatwoot_session):
        handler._process_all(payload)

    chatwoot_session.get.assert_not_called()
    # recipient skipped before send — no message POST (a label-ensure POST may still occur)
    assert not any(c.args[0].endswith('/messages') for c in chatwoot_session.post.call_args_list)


def test_unknown_instance_skips_all(handler, chatwoot_session):
    """An instance tag that has no PocketBase config must abort without any Chatwoot calls."""
    payload = MessengerPayload(
        subject='Unknown instance',
        body=TEMPLATE_BODY,
        content_type='plain',
        campaign=MessengerCampaignMeta(uuid='c-unk', name='Unknown', tags=['instance:nonexistent_xyz_9999']),
        recipients=[MessengerRecipient(uuid='r-unk', email='u@x.com', name='U', attribs={'phone': '+55'}, status='enabled')],
    )

    with patch('app.handlers.chatwoot.handler.requests.Session', return_value=chatwoot_session):
        handler._process_all(payload)

    chatwoot_session.post.assert_not_called()


def test_invalid_body_skips_all(handler, chatwoot_session):
    """A non-JSON body must cause _process_all to abort before any Chatwoot call."""
    payload = MessengerPayload(
        subject='Bad body',
        body='not valid json {{ }}',
        content_type='plain',
        campaign=MessengerCampaignMeta(uuid='c-bad', name='Bad', tags=['instance:87v79w2os56q298']),
        recipients=[MessengerRecipient(uuid='r-bad', email='b@x.com', name='B', attribs={'phone': '+55'}, status='enabled')],
    )

    with patch('app.handlers.chatwoot.handler.requests.Session', return_value=chatwoot_session):
        handler._process_all(payload)

    chatwoot_session.post.assert_not_called()


# --------------------------------------------------------------------------- #
# HTTP endpoint contract
# --------------------------------------------------------------------------- #


def test_endpoint_returns_200_immediately(client):
    """POST /v1/messenger/chat must return 200 {"status": "ok"} before processing."""
    payload = {
        'subject': 'Endpoint test',
        'body': TEMPLATE_BODY,
        'content_type': 'plain',
        'recipients': [{'uuid': 'r-ep', 'email': 'ep@x.com', 'name': 'EP', 'attribs': {'phone': '+55'}, 'status': 'enabled'}],
        'campaign': {'uuid': 'c-ep', 'name': 'EP Campaign', 'tags': ['instance:87v79w2os56q298']},
        'attachments': [],
    }

    with patch('app.handlers.chatwoot.handler.Thread') as mock_thread:
        response = client.post('/v1/messenger/chat', json=payload)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'status': 'ok'}
    mock_thread.return_value.start.assert_called_once()
