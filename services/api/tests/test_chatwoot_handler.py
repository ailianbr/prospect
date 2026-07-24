# tests/test_chatwoot_handler.py
import json
import os
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.handlers.chatwoot.handler import (
    CampaignCtx,
    ChatwootHandler,
    _campaign_labels,  # noqa: PLC2701
    _render_content,  # noqa: PLC2701
    _slug,  # noqa: PLC2701
)
from app.handlers.chatwoot.schemas import ChatwootCampaignBody, ChatwootTemplateConfig
from app.handlers.resolver import DefaultVariableResolver
from app.schemas import MessengerCampaignMeta, MessengerPayload, MessengerRecipient

# --- constants for call counts ---
CHATWOOT_CALLS_NEW_CONTACT = 4  # contact_create + conversation + labels + message
CHATWOOT_CALLS_EXIST_CONTACT = 3  # conversation + labels + message (contact found in search)
CHATWOOT_CALLS_CONVERSATION_FAILED = 2  # contact create + failed conversation (stops before labels)

# --------------------------------------------------------------------------- #
# Shared test data
# --------------------------------------------------------------------------- #

TEMPLATE_BODY = json.dumps({
    'content': 'Oi, {{1}}! Sua fatura de {{2}} venceu.',
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
                '2': 'instancia.razao_social:Empresa',
            },
            'buttons': [],
        },
    },
})

CHATWOOT_CONFIG = {
    'url': 'https://chatwoot.example.com',
    'api_token_handler': 'test_token',
    'api_token_templates': 'user_token',
    'account_id': 5,
    'inbox_id': 10,
    'phone_attr': 'phone',
}

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def handler():
    return ChatwootHandler(resolver=DefaultVariableResolver())


@pytest.fixture
def template():
    return ChatwootCampaignBody.model_validate_json(TEMPLATE_BODY).template_params


@pytest.fixture
def recipient():
    return MessengerRecipient(
        uuid='r-001',
        email='joao@example.com',
        name='João',
        attribs={'phone': '+5511999999999'},
        status='enabled',
    )


@pytest.fixture
def payload(recipient):
    return MessengerPayload(
        subject='Sua fatura venceu',
        body=TEMPLATE_BODY,
        content_type='plain',
        campaign=MessengerCampaignMeta(
            uuid='camp-001',
            name='Cobrança Nov',
            tags=['cobranca', 'instance:mxf'],
        ),
        recipients=[recipient],
    )


@pytest.fixture
def ctx(template, payload):
    return CampaignCtx(
        config=CHATWOOT_CONFIG,
        template=template,
        payload=payload,
        instancia={'razao_social': 'Empresa XYZ'},
    )


@pytest.fixture
def mock_pb():
    return MagicMock()


def _make_http_session(contact_id=42, conversation_id=99, contact_exists=False):
    """Return a mock requests.Session configured for a successful Chatwoot flow."""
    session = MagicMock()

    search_resp = MagicMock(ok=True)
    search_resp.json.return_value = {'payload': [{'id': contact_id}] if contact_exists else []}
    session.get.return_value = search_resp

    create_contact = MagicMock(ok=True)
    create_contact.json.return_value = {'id': contact_id}
    create_conv = MagicMock(ok=True)
    create_conv.json.return_value = {'id': conversation_id}
    labels_resp = MagicMock(ok=True)
    send_msg = MagicMock(ok=True)
    session.post.side_effect = [create_contact, create_conv, labels_resp, send_msg]

    return session


# --------------------------------------------------------------------------- #
# _extract_instance_id
# --------------------------------------------------------------------------- #


def test_extract_instance_id_present(handler):
    assert handler._extract_instance_id(['cobranca', 'instance:mxf']) == 'mxf'


def test_extract_instance_id_absent(handler):
    assert handler._extract_instance_id(['cobranca', 'novembro']) is None


def test_extract_instance_id_none_tags(handler):
    assert handler._extract_instance_id(None) is None


# --------------------------------------------------------------------------- #
# _process_one — happy path
# --------------------------------------------------------------------------- #


def test_process_one_success(handler, recipient, ctx):
    session = _make_http_session(contact_id=42, conversation_id=99)

    result = handler._process_one(recipient, ctx, session)

    assert result is True
    session.get.assert_called_once()
    assert session.post.call_count == CHATWOOT_CALLS_NEW_CONTACT


def test_process_one_uses_existing_contact(handler, recipient, ctx):
    session = _make_http_session(contact_id=42, conversation_id=99, contact_exists=True)

    result = handler._process_one(recipient, ctx, session)

    assert result is True
    assert session.post.call_count == CHATWOOT_CALLS_EXIST_CONTACT


# --------------------------------------------------------------------------- #
# _process_one — skip conditions
# --------------------------------------------------------------------------- #


def test_process_one_skips_when_required_field_missing(handler, payload):
    body = json.dumps({
        'name': 't',
        'language': 'pt_BR',
        'category': 'UTILITY',
        'processed_params': {'body': {'1': 'lead.attribs.cpf'}, 'buttons': []},  # required, no default
    })
    local_template = ChatwootTemplateConfig.model_validate_json(body)
    recipient = MessengerRecipient(uuid='r-002', email='a@b.com', name='X', attribs={'phone': '+55'}, status='enabled')
    local_ctx = CampaignCtx(config=CHATWOOT_CONFIG, template=local_template, payload=payload, instancia={})
    session = MagicMock()

    result = handler._process_one(recipient, local_ctx, session)

    assert result is False
    session.get.assert_not_called()
    session.post.assert_not_called()


def test_process_one_skips_when_phone_missing(handler, ctx, payload):
    recipient = MessengerRecipient(uuid='r-003', email='a@b.com', name='X', attribs={}, status='enabled')
    session = MagicMock()

    result = handler._process_one(recipient, ctx, session)

    assert result is False
    session.get.assert_not_called()


def test_process_one_skips_when_contact_create_fails(handler, recipient, ctx):
    session = MagicMock()
    session.get.return_value = MagicMock(ok=True, json=lambda: {'payload': []})
    session.post.return_value = MagicMock(ok=False)

    result = handler._process_one(recipient, ctx, session)

    assert result is False
    assert session.post.call_count == 1  # only contact create attempted


def test_process_one_skips_when_conversation_fails(handler, recipient, ctx):
    session = MagicMock()
    session.get.return_value = MagicMock(ok=True, json=lambda: {'payload': []})
    ok_contact = MagicMock(ok=True, json=lambda: {'id': 42})
    fail_conv = MagicMock(ok=False)
    session.post.side_effect = [ok_contact, fail_conv]

    result = handler._process_one(recipient, ctx, session)

    assert result is False
    assert session.post.call_count == CHATWOOT_CALLS_CONVERSATION_FAILED


# --------------------------------------------------------------------------- #
# _process_all — batch flow
# --------------------------------------------------------------------------- #


def test_process_all_sends_to_chatwoot(handler, payload, mock_pb):
    session = _make_http_session(contact_id=1, conversation_id=2)

    with (
        patch('app.handlers.chatwoot.handler.get_pocketbase_session', return_value=mock_pb),
        patch('app.handlers.chatwoot.handler.fetch_chatwoot_config', return_value=CHATWOOT_CONFIG),
        patch('app.handlers.chatwoot.handler.requests.Session', return_value=session),
        patch.object(ChatwootHandler, '_ensure_labels'),
    ):
        handler._process_all(payload)

    assert session.post.call_count == CHATWOOT_CALLS_NEW_CONTACT


def test_process_all_invalid_body_skips_all(handler, mock_pb):
    bad_payload = MessengerPayload(
        subject='S',
        body='not valid json',
        content_type='plain',
        campaign=MessengerCampaignMeta(uuid='c', name='C', tags=['instance:mxf']),
        recipients=[MessengerRecipient(uuid='r', email='a@b.com', name='X', attribs={}, status='enabled')],
    )

    with (
        patch('app.handlers.chatwoot.handler.get_pocketbase_session', return_value=mock_pb),
        patch('app.handlers.chatwoot.handler.fetch_chatwoot_config', return_value=CHATWOOT_CONFIG),
        patch('app.handlers.chatwoot.handler.requests.Session') as mock_session_cls,
    ):
        handler._process_all(bad_payload)

    mock_session_cls.return_value.post.assert_not_called()


def test_process_all_missing_instance_tag_skips_all(handler, mock_pb):
    payload_no_tag = MessengerPayload(
        subject='S',
        body=TEMPLATE_BODY,
        content_type='plain',
        campaign=MessengerCampaignMeta(uuid='c', name='C', tags=['cobranca']),
        recipients=[MessengerRecipient(uuid='r', email='a@b.com', name='X', attribs={}, status='enabled')],
    )

    with (
        patch('app.handlers.chatwoot.handler.get_pocketbase_session', return_value=mock_pb),
        patch('app.handlers.chatwoot.handler.fetch_chatwoot_config', return_value=CHATWOOT_CONFIG),
        patch('app.handlers.chatwoot.handler.requests.Session') as mock_session_cls,
    ):
        handler._process_all(payload_no_tag)

    mock_session_cls.return_value.post.assert_not_called()


def test_process_all_missing_config_skips_all(handler, payload):
    with (
        patch('app.handlers.chatwoot.handler.get_pocketbase_session', return_value=MagicMock()),
        patch('app.handlers.chatwoot.handler.fetch_chatwoot_config', return_value=None),
        patch('app.handlers.chatwoot.handler.requests.Session') as mock_session_cls,
    ):
        handler._process_all(payload)

    mock_session_cls.return_value.post.assert_not_called()


def test_process_all_one_failure_does_not_abort_others(handler, mock_pb):
    """RNF-02: a failed recipient must not prevent processing of remaining recipients."""
    r_ok = MessengerRecipient(uuid='r-ok', email='ok@x.com', name='OK', attribs={'phone': '+5511111111111'}, status='enabled')
    r_no_phone = MessengerRecipient(uuid='r-skip', email='skip@x.com', name='Skip', attribs={}, status='enabled')
    multi_payload = MessengerPayload(
        subject='S',
        body=TEMPLATE_BODY,
        content_type='plain',
        campaign=MessengerCampaignMeta(uuid='c', name='C', tags=['instance:mxf']),
        recipients=[r_no_phone, r_ok],
    )

    session = _make_http_session(contact_id=1, conversation_id=2)

    with (
        patch('app.handlers.chatwoot.handler.get_pocketbase_session', return_value=mock_pb),
        patch('app.handlers.chatwoot.handler.fetch_chatwoot_config', return_value=CHATWOOT_CONFIG),
        patch('app.handlers.chatwoot.handler.requests.Session', return_value=session),
        patch.object(ChatwootHandler, '_ensure_labels'),
    ):
        handler._process_all(multi_payload)

    # r_ok: contact_create + conversation + message; r_no_phone: no calls
    assert session.post.call_count == CHATWOOT_CALLS_NEW_CONTACT


# --------------------------------------------------------------------------- #
# send() — background thread
# --------------------------------------------------------------------------- #


def test_send_starts_background_thread(handler, payload):
    with patch('app.handlers.chatwoot.handler.Thread') as mock_thread:
        handler.send(payload)
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()


# --------------------------------------------------------------------------- #
# E2E — real PocketBase + real Chatwoot (requires env vars via Doppler)
# --------------------------------------------------------------------------- #


class _SyncThread:
    """Replaces threading.Thread to run the target synchronously for test assertions."""

    def __init__(self, target, args=(), daemon=False):
        self._target = target
        self._args = args

    def start(self):
        self._target(*self._args)


_E2E_VARS = ['TEST_CHATWOOT_INSTANCE_ID', 'TEST_CHATWOOT_PHONE', 'TEST_CHATWOOT_TEMPLATE']


@pytest.mark.skipif(
    not all(os.getenv(v) for v in _E2E_VARS),
    reason='requires TEST_CHATWOOT_INSTANCE_ID, TEST_CHATWOOT_PHONE, TEST_CHATWOOT_TEMPLATE',
)
def test_chatwoot_e2e_sends_via_messenger(client):
    """E2E: POST /v1/messenger/chat runs through real PocketBase and Chatwoot API."""
    instance_id = os.environ['TEST_CHATWOOT_INSTANCE_ID']
    phone = os.environ['TEST_CHATWOOT_PHONE']
    template = os.environ['TEST_CHATWOOT_TEMPLATE']

    body = json.dumps({
        'content': '',
        'message_type': 'outgoing',
        'private': False,
        'content_type': 'text',
        'template_params': {
            'name': template,
            'language': 'pt_BR',
            'category': 'UTILITY',
            'processed_params': {'body': {}, 'buttons': []},
        },
    })
    payload = {
        'subject': 'E2E Test',
        'body': body,
        'content_type': 'plain',
        'campaign': {
            'uuid': 'e2e-test-001',
            'name': 'E2E Chatwoot Test',
            'tags': [f'instance:{instance_id}'],
        },
        'recipients': [
            {
                'uuid': 'e2e-recipient-001',
                'email': 'test@example.com',
                'name': 'Test Contact',
                'attribs': {'phone': phone},
                'status': 'enabled',
            }
        ],
    }

    captured = {}

    with (
        patch('app.handlers.chatwoot.handler.Thread', _SyncThread),
        patch('app.handlers.chatwoot.handler.enrich_wide_event', side_effect=captured.update),
    ):
        response = client.post('/v1/messenger/chat', json=payload)

    assert response.status_code == HTTPStatus.OK
    assert 'error' not in captured, f'Handler reported error: {captured}'
    assert captured.get('recipients_sent') == 1


# --------------------------------------------------------------------------- #
# Campaign labels
# --------------------------------------------------------------------------- #


def test_slug_strips_accents_and_specials():
    assert _slug('Cobrança Nov') == 'cobranca_nov'
    assert _slug('Black Friday 2026!') == 'black_friday_2026'
    assert _slug('  --VIP--  ') == 'vip'
    assert not _slug('')


def test_campaign_labels_name_plus_tags_drops_instance_and_dedups():
    payload = MessengerPayload(
        subject='S',
        body=TEMPLATE_BODY,
        content_type='plain',
        campaign=MessengerCampaignMeta(uuid='c', name='Teste 23', tags=['vip', 'instance:mxf', 'vip']),
        recipients=[],
    )
    assert _campaign_labels(payload) == ['campanha_teste_23', 'vip']


def test_process_one_tags_conversation_with_campaign_labels(handler, recipient, ctx):
    session = _make_http_session(contact_id=42, conversation_id=99)

    handler._process_one(recipient, ctx, session)

    label_calls = [c for c in session.post.call_args_list if c.args and c.args[0].endswith('/conversations/99/labels')]
    assert label_calls, 'expected a POST to the conversation labels endpoint'
    assert label_calls[0].kwargs['json'] == {'labels': ['campanha_cobranca_nov', 'cobranca']}


def test_process_one_label_failure_is_non_fatal(handler, recipient, ctx):
    session = _make_http_session(contact_id=42, conversation_id=99)
    create_contact = MagicMock(ok=True, json=lambda: {'id': 42})
    create_conv = MagicMock(ok=True, json=lambda: {'id': 99})
    labels_fail = MagicMock(ok=False, status_code=422, text='nope')
    send_msg = MagicMock(ok=True)
    session.post.side_effect = [create_contact, create_conv, labels_fail, send_msg]

    result = handler._process_one(recipient, ctx, session)

    assert result is True  # a labels failure must not block the message send
    assert session.post.call_count == CHATWOOT_CALLS_NEW_CONTACT


def test_ensure_labels_creates_account_labels_idempotently(handler):
    session = MagicMock()
    created = MagicMock(ok=True)
    already = MagicMock(ok=False, status_code=HTTPStatus.UNPROCESSABLE_ENTITY, text='taken')  # existing -> tolerated
    session.post.side_effect = [created, already]
    labels = ['campanha_x', 'vip']

    handler._ensure_labels(session, CHATWOOT_CONFIG, labels)

    assert session.post.call_count == len(labels)
    assert all(c.args[0].endswith('/labels') for c in session.post.call_args_list)
    assert [c.kwargs['json']['title'] for c in session.post.call_args_list] == labels


def test_process_one_label_exception_is_non_fatal(handler, recipient, ctx):
    """A raised exception on the label call must not abort the send (message still goes out)."""
    session = MagicMock()
    session.get.return_value = MagicMock(ok=True, json=lambda: {'payload': []})

    def _post(url, *args, **kwargs):
        if url.endswith('/labels'):
            raise requests.ConnectionError('boom')
        resp = MagicMock(ok=True)
        resp.json.return_value = {'id': 42} if url.endswith('/contacts') else {'id': 99}
        return resp

    session.post.side_effect = _post

    result = handler._process_one(recipient, ctx, session)

    assert result is True  # label exception is swallowed; the template message still sends
    assert any(c.args[0].endswith('/messages') for c in session.post.call_args_list)


# --------------------------------------------------------------------------- #
# Message content rendering (so the message text shows in the Chatwoot UI)
# --------------------------------------------------------------------------- #


def test_render_content_substitutes_placeholders():
    body = 'Oi, {{1}}! Sua fatura de {{2}} venceu.'
    assert _render_content(body, {'1': 'João', '2': 'Novembro'}) == 'Oi, João! Sua fatura de Novembro venceu.'
    assert _render_content('{{ 1 }}', {'1': 'x'}) == 'x'  # tolerates whitespace in the placeholder
    assert _render_content('preço: {{1}}', {'1': 'R$ 10\\3'}) == 'preço: R$ 10\\3'  # value not regex-interpreted
    assert not _render_content('', {'1': 'x'})
    assert _render_content('no vars here', {}) == 'no vars here'


def test_build_message_body_renders_content(template):
    body = ChatwootHandler._build_message_body(template, {'1': 'João', '2': 'Empresa'}, [], 'Oi, {{1}} da {{2}}.')
    assert body['content'] == 'Oi, João da Empresa.'
    assert body['template_params']['name'] == template.name


def test_fetch_template_body_returns_body_text(handler):
    session = MagicMock()
    session.get.return_value = MagicMock(
        ok=True,
        json=lambda: {
            'payload': [
                {
                    'message_templates': [
                        {'name': 'other', 'components': [{'type': 'BODY', 'text': 'nope'}]},
                        {
                            'name': 'cobranca_v2',
                            'components': [{'type': 'HEADER', 'text': 'h'}, {'type': 'BODY', 'text': 'Oi, {{1}}!'}],
                        },
                    ]
                }
            ]
        },
    )
    assert handler._fetch_template_body(session, CHATWOOT_CONFIG, 'cobranca_v2') == 'Oi, {{1}}!'


def test_fetch_template_body_missing_returns_empty(handler):
    session = MagicMock()
    session.get.return_value = MagicMock(ok=True, json=lambda: {'payload': []})
    assert not handler._fetch_template_body(session, CHATWOOT_CONFIG, 'nope')
