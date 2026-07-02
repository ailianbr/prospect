#!/usr/bin/env python3
"""Dev one-shot: idempotently import the PocketBase control-plane schema.

Mirrors conectai's `pb-init`: authenticate as the superuser that the muchobien
image bootstraps from PB_ADMIN_EMAIL/PB_ADMIN_PASSWORD, then PUT the collections
export. Re-running is a no-op upsert (deleteMissing=false never drops anything),
so it is safe on every `docker compose up`.

Stdlib only (runs in a bare python:alpine container). Reads:
  PB_URL              base PocketBase URL (e.g. http://pocketbase:8090)
  PB_ADMIN_EMAIL      superuser identity (the app's POCKETBASE_BOT_EMAIL)
  PB_ADMIN_PASSWORD   superuser password (the app's POCKETBASE_BOT_PASSWORD)
  SCHEMA_PATH         collections export to import (default /schema.json)
"""

import json
import os
import sys
import urllib.error
import urllib.request

PB = os.environ['PB_URL'].rstrip('/')
EMAIL = os.environ['PB_ADMIN_EMAIL']
PASSWORD = os.environ['PB_ADMIN_PASSWORD']
SCHEMA_PATH = os.environ.get('SCHEMA_PATH', '/schema.json')


def _req(method: str, path: str, body=None, token: str | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(PB + path, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', token)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read() or b'{}')


def main() -> None:
    auth = _req(
        'POST',
        '/api/collections/_superusers/auth-with-password',
        {'identity': EMAIL, 'password': PASSWORD},
    )
    token = auth['token']

    with open(SCHEMA_PATH) as fh:
        collections = json.load(fh)

    _req('PUT', '/api/collections/import', {'collections': collections, 'deleteMissing': False}, token=token)
    print(f'pb-init: imported {len(collections)} collections into {PB}')


if __name__ == '__main__':
    try:
        main()
    except urllib.error.HTTPError as e:
        sys.exit(f'pb-init FAILED: HTTP {e.code} {e.read().decode()[:300]}')
    except (urllib.error.URLError, KeyError, OSError) as e:
        sys.exit(f'pb-init FAILED: {e}')
