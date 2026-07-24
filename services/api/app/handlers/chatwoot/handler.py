import logging
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from http import HTTPStatus
from threading import Thread
from typing import override

import requests
from pocketbase.errors import ClientResponseError

from app.context import enrich_wide_event
from app.handlers.base import MessengerHandlerBase, VariableResolverBase
from app.handlers.chatwoot.schemas import ChatwootCampaignBody, ChatwootTemplateConfig
from app.schemas import MessengerPayload, MessengerRecipient
from app.sessions import get_pocketbase_session

logger = logging.getLogger(__name__)

# Keys within service_secrets.secret_config — update here if field names change
# Note: Chatwoot restricts bot tokens from contact endpoints; user token required for handler
_HANDLER_TOKEN_KEY = 'api_access_token_user'
_TEMPLATES_TOKEN_KEY = 'api_access_token_user'

# Neutral color for auto-created campaign labels (Chatwoot requires a color on create).
_LABEL_COLOR = '#8c9dad'


def _slug(text: str) -> str:
    """Normalize text into a Chatwoot label: strip accents, lowercase, non-alphanumeric -> `_`."""
    ascii_text = unicodedata.normalize('NFKD', text or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '_', ascii_text.lower()).strip('_')


def _campaign_labels(payload: MessengerPayload) -> list[str]:
    """Chatwoot labels for a campaign's conversations: `campanha_<name>` plus the campaign's
    front-set tags (the internal `instance:<id>` tag excluded). Deduped, order-stable."""
    labels: list[str] = []
    name = _slug(payload.campaign.name)
    if name:
        labels.append(f'campanha_{name}')
    for tag in payload.campaign.tags or []:
        if tag.startswith('instance:'):
            continue
        slug = _slug(tag)
        if slug:
            labels.append(slug)
    seen: set[str] = set()
    return [x for x in labels if not (x in seen or seen.add(x))]


def _render_content(body_text: str, resolved_body: dict[str, str]) -> str:
    """Fill a WhatsApp template's BODY text (`Oi, {{1}}! ...`) with the resolved values so the
    outgoing Chatwoot message shows real text — `create_campaign` clears the content before Listmonk
    (the `{{n}}` would break its Go-template compiler), so we render it here for display."""
    text = body_text or ''
    for slot, value in resolved_body.items():
        text = re.sub(r'\{\{\s*' + re.escape(slot) + r'\s*\}\}', lambda _m, v=value: v, text)
    return text


def _template_body_text(template: dict) -> str:
    """Extract the BODY component text from a Chatwoot message-template object."""
    for comp in template.get('components', []):
        if (comp.get('type') or '').upper() == 'BODY':
            return comp.get('text') or ''
    return ''


def fetch_chatwoot_config(pb, instance_id: str, handler: str, channel: str) -> dict | None:
    """Assemble Chatwoot connection config from multiple PocketBase collections.

    Returns a dict with keys: url, account_id, inbox_id, phone_attr,
    api_token_handler, api_token_templates. Returns None if any required
    collection lookup fails.
    """
    ctx = {'instance_id': instance_id, 'handler': handler, 'channel': channel}
    try:
        channel_record = pb.client.collection('monk_channel_configs').get_first_list_item(
            f'instance_id="{instance_id}" && handler="{handler}" && channel="{channel}"'
        )
    except ClientResponseError as e:
        logger.warning('chatwoot.config_missing', extra={**ctx, 'collection': 'monk_channel_configs', 'status': e.status})
        return None
    extra = channel_record.extra_config

    try:
        instance_svc = pb.client.collection('instance_services').get_first_list_item(
            f'instance="{instance_id}" && service.key="{handler}"'
        )
    except ClientResponseError as e:
        logger.warning('chatwoot.config_missing', extra={**ctx, 'collection': 'instance_services', 'status': e.status})
        return None

    try:
        secret_record = pb.client.collection('service_secrets').get_first_list_item(f'instance_service="{instance_svc.id}"')
    except ClientResponseError as e:
        logger.warning(
            'chatwoot.config_missing',
            extra={**ctx, 'collection': 'service_secrets', 'svc_id': instance_svc.id, 'pb_status': e.status},
        )
        return None
    secret = secret_record.secret_config

    try:
        svc_config = pb.client.collection('common_service_config').get_first_list_item(f'service.key="{handler}"')
    except ClientResponseError as e:
        logger.warning('chatwoot.config_missing', extra={**ctx, 'collection': 'common_service_config', 'status': e.status})
        return None

    try:
        instance_config = pb.client.collection('conectai_instance_config').get_first_list_item(f'instance="{instance_id}"')
    except ClientResponseError as e:
        logger.warning('chatwoot.config_missing', extra={**ctx, 'collection': 'conectai_instance_config', 'status': e.status})
        return None

    return {
        'url': svc_config.service_url,
        'account_id': instance_config.chatwoot_account_id,
        'inbox_id': extra['inbox_id'],
        'phone_attr': extra['phone_attr'],
        'api_token_handler': secret[_HANDLER_TOKEN_KEY],
        'api_token_templates': secret[_TEMPLATES_TOKEN_KEY],
    }


@dataclass
class CampaignCtx:
    """Holds campaign-level data shared across all recipients in one send() call."""

    config: dict
    template: ChatwootTemplateConfig
    payload: MessengerPayload
    instancia: dict
    content_template: str = ''  # approved template BODY text ({{n}}), fetched from Chatwoot for display


class ChatwootHandler(MessengerHandlerBase):
    def __init__(self, resolver: VariableResolverBase) -> None:
        self._resolver = resolver

    @override
    def send(self, payload: MessengerPayload) -> None:
        """Return immediately; process recipients in a background thread (PROB-06)."""
        Thread(target=self._process_all, args=(payload,), daemon=True).start()

    # ------------------------------------------------------------------ #
    # PocketBase helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_instance_id(tags: list[str] | None) -> str | None:
        for tag in tags or []:
            if tag.startswith('instance:'):
                return tag.split(':', 1)[1]
        return None

    @staticmethod
    def _fetch_instancia(pb, instance_id: str) -> dict:
        try:
            record = pb.client.collection('instances').get_one(instance_id)
            return {k: v for k, v in record.__dict__.items() if not k.startswith('_')}
        except Exception:
            return {}

    # ------------------------------------------------------------------ #
    # Chatwoot API calls
    # ------------------------------------------------------------------ #

    @staticmethod
    def _headers(api_token: str) -> dict:
        return {'api_access_token': api_token, 'Content-Type': 'application/json'}

    def _find_or_create_contact(self, session: requests.Session, config: dict, phone: str, name: str) -> int | None:
        base = f'{config["url"].rstrip("/")}/api/v1/accounts/{config["account_id"]}'
        headers = self._headers(config['api_token_handler'])

        resp = session.get(
            f'{base}/contacts/search',
            params={'q': phone, 'include_contacts': 'true'},
            headers=headers,
            timeout=10,
        )
        if resp.ok:
            results = resp.json().get('payload', [])
            if results:
                return results[0]['id']
        else:
            logger.warning('chatwoot.contact_search_failed', extra={'status': resp.status_code, 'body': resp.text[:500]})

        resp = session.post(
            f'{base}/contacts',
            json={'name': name, 'phone_number': phone},
            headers=headers,
            timeout=10,
        )
        if not resp.ok:
            logger.error('chatwoot.create_contact_failed', extra={'status': resp.status_code, 'body': resp.text[:500]})
            return None
        return resp.json().get('id')

    def _create_conversation(self, session: requests.Session, config: dict, contact_id: int) -> int | None:
        base = f'{config["url"].rstrip("/")}/api/v1/accounts/{config["account_id"]}'
        resp = session.post(
            f'{base}/conversations',
            json={'inbox_id': config['inbox_id'], 'contact_id': contact_id},
            headers=self._headers(config['api_token_handler']),
            timeout=10,
        )
        if not resp.ok:
            logger.error('chatwoot.create_conversation_failed', extra={'status': resp.status_code, 'body': resp.text[:500]})
            return None
        return resp.json().get('id')

    def _ensure_labels(self, session: requests.Session, config: dict, labels: list[str]) -> None:
        """Create each label as an account Label so it is filterable in Chatwoot (a conversation-only
        tag is not). Idempotent: Chatwoot returns 422 'already taken' for existing labels, treated as
        success. Called once per campaign; non-fatal."""
        base = f'{config["url"].rstrip("/")}/api/v1/accounts/{config["account_id"]}'
        headers = self._headers(config['api_token_handler'])
        for label in labels:
            try:
                resp = session.post(
                    f'{base}/labels',
                    json={'title': label, 'color': _LABEL_COLOR},
                    headers=headers,
                    timeout=10,
                )
                if not resp.ok and resp.status_code != HTTPStatus.UNPROCESSABLE_ENTITY:
                    logger.warning(
                        'chatwoot.label_create_failed',
                        extra={'status': resp.status_code, 'body': resp.text[:300], 'label': label},
                    )
            except requests.RequestException as e:
                logger.warning('chatwoot.label_create_failed', extra={'error': str(e), 'label': label})

    def _add_conversation_labels(
        self, session: requests.Session, config: dict, conversation_id: int, labels: list[str]
    ) -> bool:
        """Tag the conversation so campaigns are filterable in Chatwoot. Non-fatal: a failure is
        logged and never blocks the send."""
        if not labels:
            return True
        base = f'{config["url"].rstrip("/")}/api/v1/accounts/{config["account_id"]}'
        try:
            resp = session.post(
                f'{base}/conversations/{conversation_id}/labels',
                json={'labels': labels},
                headers=self._headers(config['api_token_handler']),
                timeout=10,
            )
        except requests.RequestException as e:
            logger.warning('chatwoot.label_failed', extra={'error': str(e), 'labels': labels})
            return False
        if not resp.ok:
            logger.warning(
                'chatwoot.label_failed',
                extra={'status': resp.status_code, 'body': resp.text[:500], 'labels': labels},
            )
        return resp.ok

    def _fetch_template_body(self, session: requests.Session, config: dict, template_name: str) -> str:
        """Return the approved WhatsApp template's BODY text (with `{{n}}`) from Chatwoot, so we can
        render it into the message `content`. Non-fatal: returns '' on any failure (the message still
        sends, just without visible text in the Chatwoot UI)."""
        base = f'{config["url"].rstrip("/")}/api/v1/accounts/{config["account_id"]}'
        try:
            resp = session.get(f'{base}/inboxes', headers=self._headers(config['api_token_templates']), timeout=10)
        except requests.RequestException as e:
            logger.warning('chatwoot.template_fetch_failed', extra={'error': str(e), 'template': template_name})
            return ''
        if not resp.ok:
            return ''
        for inbox in resp.json().get('payload', []):
            for tpl in inbox.get('message_templates', []):
                if tpl.get('name') == template_name:
                    return _template_body_text(tpl)
        return ''

    @staticmethod
    def _build_message_body(template, resolved_body: dict, resolved_buttons: list, content_template: str = '') -> dict:
        processed_params: dict = dict(resolved_body)
        if resolved_buttons:
            processed_params['buttons'] = resolved_buttons
        return {
            'content': _render_content(content_template, resolved_body),
            'template_params': {
                'name': template.name,
                'category': template.category,
                'language': template.language,
                'processed_params': processed_params,
            },
        }

    def _send_template_message(self, session: requests.Session, config: dict, conversation_id: int, message_body: dict) -> bool:
        base = f'{config["url"].rstrip("/")}/api/v1/accounts/{config["account_id"]}'
        resp = session.post(
            f'{base}/conversations/{conversation_id}/messages',
            json=message_body,
            headers=self._headers(config['api_token_handler']),
            timeout=10,
        )
        if not resp.ok:
            logger.error('chatwoot.send_message_failed', extra={'status': resp.status_code, 'body': resp.text[:500]})
        return resp.ok

    # ------------------------------------------------------------------ #
    # Per-recipient processing
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_context(recipient: MessengerRecipient, ctx: CampaignCtx) -> dict:
        return {
            'lead': {
                'uuid': recipient.uuid,
                'email': recipient.email,
                'name': recipient.name,
                'status': recipient.status,
                'attribs': recipient.attribs,
            },
            'campanha': {
                'uuid': ctx.payload.campaign.uuid,
                'name': ctx.payload.campaign.name,
                'subject': ctx.payload.subject,  # top-level payload field covers PROB-01
                'tags': ctx.payload.campaign.tags or [],
            },
            'instancia': ctx.instancia,
        }

    def _resolve_params(self, recipient: MessengerRecipient, ctx: CampaignCtx) -> tuple[dict, list] | None:
        """Resolve all template variable refs. Returns None if any required field is absent."""
        context = self._build_context(recipient, ctx)
        log_ctx = {'uuid': recipient.uuid, 'campaign': ctx.payload.campaign.name}

        resolved_body: dict[str, str] = {}
        for slot, ref in ctx.template.processed_params.body.items():
            ok, value = self._resolver.resolve(ref, context)
            if not ok:
                logger.warning('chatwoot.skip_recipient', extra={**log_ctx, 'reason': f'missing:{ref}'})
                return None
            resolved_body[slot] = value

        resolved_buttons: list[dict] = []
        for btn in ctx.template.processed_params.buttons:
            ok, value = self._resolver.resolve(btn.parameter, context)
            if not ok:
                logger.warning('chatwoot.skip_recipient', extra={**log_ctx, 'reason': f'missing:{btn.parameter}'})
                return None
            resolved_buttons.append({'type': btn.type, 'parameter': value, 'url': btn.url, 'variables': btn.variables})

        return resolved_body, resolved_buttons

    def _process_one(self, recipient: MessengerRecipient, ctx: CampaignCtx, session: requests.Session) -> bool:
        resolved = self._resolve_params(recipient, ctx)
        if resolved is None:
            return False

        resolved_body, resolved_buttons = resolved
        log_ctx = {'uuid': recipient.uuid, 'campaign': ctx.payload.campaign.name}

        phone = recipient.attribs.get(ctx.config['phone_attr'])
        if not phone:
            logger.warning('chatwoot.skip_recipient', extra={**log_ctx, 'reason': 'missing:phone'})
            return False

        contact_id = self._find_or_create_contact(session, ctx.config, str(phone), recipient.name)
        if contact_id is None:
            return False

        conversation_id = self._create_conversation(session, ctx.config, contact_id)
        if conversation_id is None:
            return False

        self._add_conversation_labels(session, ctx.config, conversation_id, _campaign_labels(ctx.payload))

        message_body = self._build_message_body(ctx.template, resolved_body, resolved_buttons, ctx.content_template)
        if not self._send_template_message(session, ctx.config, conversation_id, message_body):
            return False

        return True

    # ------------------------------------------------------------------ #
    # Batch processing (runs in daemon thread)
    # ------------------------------------------------------------------ #

    def _process_all(self, payload: MessengerPayload) -> None:
        # Parse template config from body (PROB-05)
        try:
            campaign_body = ChatwootCampaignBody.model_validate_json(payload.body)
            template = campaign_body.template_params
        except Exception as exc:
            logger.error('chatwoot.invalid_body', extra={'error': str(exc)})
            enrich_wide_event({
                'handler': 'chatwoot',
                'error': 'invalid_body',
                'recipients_total': len(payload.recipients),
                'recipients_sent': 0,
                'recipients_skipped': len(payload.recipients),
            })
            return

        # Extract instance_id from campaign tags (ALT-A from PROB-03)
        instance_id = self._extract_instance_id(payload.campaign.tags)
        if not instance_id:
            logger.error('chatwoot.missing_instance_id', extra={'campaign': payload.campaign.uuid})
            enrich_wide_event({
                'handler': 'chatwoot',
                'error': 'missing_instance_id',
                'recipients_total': len(payload.recipients),
                'recipients_sent': 0,
                'recipients_skipped': len(payload.recipients),
            })
            return

        pb = get_pocketbase_session()
        config = fetch_chatwoot_config(pb, instance_id, handler='chat', channel='whatsapp')
        if config is None:
            logger.error('chatwoot.missing_config', extra={'instance_id': instance_id})
            enrich_wide_event({
                'handler': 'chatwoot',
                'error': 'missing_config',
                'recipients_total': len(payload.recipients),
                'recipients_sent': 0,
                'recipients_skipped': len(payload.recipients),
            })
            return

        session = requests.Session()
        ctx = CampaignCtx(
            config=config,
            template=template,
            payload=payload,
            instancia=self._fetch_instancia(pb, instance_id),
            content_template=self._fetch_template_body(session, config, template.name),
        )
        # Register the campaign labels as account Labels once (so they're filterable), then the
        # per-recipient fan-out just assigns them to each conversation.
        self._ensure_labels(session, config, _campaign_labels(payload))

        def _safe_process(recipient: MessengerRecipient) -> bool:
            # Never let one recipient's unexpected error abort the batch or vanish silently.
            try:
                return self._process_one(recipient, ctx, session)
            except Exception:
                logger.exception('chatwoot.recipient_error', extra={'uuid': recipient.uuid, 'campaign': payload.campaign.name})
                return False

        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(_safe_process, payload.recipients))

        sent_count = sum(1 for r in results if r)
        skipped_count = sum(1 for r in results if not r)

        enrich_wide_event({
            'handler': 'chatwoot',
            'campaign': payload.campaign.name,
            'recipients_total': len(payload.recipients),
            'recipients_sent': sent_count,
            'recipients_skipped': skipped_count,
        })
