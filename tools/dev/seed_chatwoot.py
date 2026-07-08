#!/usr/bin/env python3
"""Dev one-shot: seed the Chatwoot instance graph in PocketBase (idempotent).

The /messenger/chat handler (app/handlers/chatwoot/handler.py) assembles a tenant's
Chatwoot config from six collections. This seeds one fully-wired test instance
(default id 87v79w2os56q298 — the id the chatwoot tests use) so the chatwoot
integration + channel tests run green. The Chatwoot API itself is mocked in those
tests, so the api_access_token here is a placeholder.

Requires the chatwoot collections to exist (imported by pb_init.py from the dev
schema). Stdlib only. Reads PB_URL, PB_ADMIN_EMAIL, PB_ADMIN_PASSWORD,
TEST_CHATWOOT_INSTANCE_ID (default 87v79w2os56q298).
"""

import json
import os
import sys
import urllib.error
import urllib.request

PB = os.environ['PB_URL'].rstrip('/')
EMAIL = os.environ['PB_ADMIN_EMAIL']
PASSWORD = os.environ['PB_ADMIN_PASSWORD']
IID = os.environ.get('TEST_CHATWOOT_INSTANCE_ID', '87v79w2os56q298')

# fixed 15-char ids (^[a-z0-9]+$) so the graph is deterministic + idempotent
SVC = 'chatsvc00000001'
INSTSVC = 'chatinstsvc0001'

# (collection, record) in dependency order
RECORDS = [
    ('instances', {'id': IID, 'name': 'Test Instance (chatwoot)', 'type': 'client', 'key': 'mxf'}),
    ('services', {'id': SVC, 'name': 'Chat', 'key': 'chat', 'translations': {'pt-BR': 'Chat', 'en': 'Chat'}}),
    ('instance_services', {'id': INSTSVC, 'instance': IID, 'service': SVC, 'is_active': True, 'provisioning_status': 'ready'}),
    ('service_secrets', {'id': 'chatsecret00001', 'instance_service': INSTSVC, 'key': 'chatwoot',
                         'secret_config': {'api_access_token_user': 'test-chatwoot-token'}}),
    ('common_service_config', {'id': 'chatcommon00001', 'service': SVC, 'service_url': 'http://chatwoot.local', 'version': 2}),
    ('conectai_instance_config', {'id': 'chatcfg00000001', 'instance': IID, 'service': SVC, 'chatwoot_account_id': '1'}),
    ('monk_channel_configs', {'id': 'chatchannel0001', 'instance_id': IID, 'handler': 'chat', 'channel': 'whatsapp',
                              'extra_config': {'inbox_id': 1, 'phone_attr': 'phone'}}),
]


def _req(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(PB + path, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', token)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, json.loads(resp.read() or b'{}')


def _exists(col, rid, token):
    try:
        _req('GET', f'/api/collections/{col}/records/{rid}', token=token)
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


def main():
    _, auth = _req('POST', '/api/collections/_superusers/auth-with-password',
                   {'identity': EMAIL, 'password': PASSWORD})
    token = auth['token']
    for col, rec in RECORDS:
        if _exists(col, rec['id'], token):
            print(f'  skip {col}/{rec["id"]} (exists)')
            continue
        _req('POST', f'/api/collections/{col}/records', rec, token=token)
        print(f'  create {col}/{rec["id"]}')
    print(f'seed-chatwoot: instance {IID} wired (handler=chat channel=whatsapp)')


if __name__ == '__main__':
    try:
        main()
    except urllib.error.HTTPError as e:
        sys.exit(f'seed-chatwoot FAILED: HTTP {e.code} {e.read().decode()[:400]}')
    except (urllib.error.URLError, KeyError, OSError) as e:
        sys.exit(f'seed-chatwoot FAILED: {e}')
