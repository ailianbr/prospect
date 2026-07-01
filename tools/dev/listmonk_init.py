#!/usr/bin/env python3
"""Dev one-shot: provision a Listmonk API user and write its creds to .env.local.

Listmonk (v6) issues an API user's token exactly once — at creation — so there is
no way to "read it back" on a later run. This deletes any existing API user and
recreates it to mint a fresh token each `up`, then writes LISTMONK_USER /
LISTMONK_TOKEN to the env file the dev `api` container loads (`env_file: .env.local`).

This is prospect's analogue of conectai's `.env.full` pattern: a seed step that
discovers a value the app needs at runtime and hands it over via an env file.

Flow (verified against listmonk v6.2): form-login at /admin/login -> session cookie
-> create a type=api user with the Super Admin role -> token returned in `password`.

Stdlib only (runs in a bare python:alpine container). Reads:
  LISTMONK_URL              root URL (e.g. http://listmonk_app:9000) — NOT the /api base
  LISTMONK_ADMIN_USER       super-admin username (compose LISTMONK_ADMIN_USER)
  LISTMONK_ADMIN_PASSWORD   super-admin password (compose LISTMONK_ADMIN_PASSWORD)
  LISTMONK_API_USERNAME     api user to create (default monk_api)
  ENV_LOCAL_PATH            env file to write (default /repo/.env.local)
"""

import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

LM = os.environ['LISTMONK_URL'].rstrip('/')
ADMIN_USER = os.environ['LISTMONK_ADMIN_USER']
ADMIN_PASSWORD = os.environ['LISTMONK_ADMIN_PASSWORD']
API_USERNAME = os.environ.get('LISTMONK_API_USERNAME', 'monk_api')
ENV_LOCAL_PATH = os.environ.get('ENV_LOCAL_PATH', '/repo/.env.local')

_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def _open(method: str, path: str, body=None, form=None):
    if form is not None:
        data, ctype = urllib.parse.urlencode(form).encode(), 'application/x-www-form-urlencoded'
    elif body is not None:
        data, ctype = json.dumps(body).encode(), 'application/json'
    else:
        data, ctype = None, None
    req = urllib.request.Request(LM + path, data=data, method=method)
    if ctype:
        req.add_header('Content-Type', ctype)
    with _opener.open(req, timeout=30) as resp:
        raw = resp.read()
    return json.loads(raw) if raw and raw[:1] in b'{[' else {}


def _super_admin_role_id() -> int:
    roles = _open('GET', '/api/roles/users').get('data', [])
    for r in roles:
        if r.get('name') == 'Super Admin':
            return r['id']
    return 1  # install default


def main() -> None:
    # /admin/login 302-redirects on success; the opener follows it and keeps the cookie.
    _open('POST', '/admin/login', form={'username': ADMIN_USER, 'password': ADMIN_PASSWORD})

    # this also proves the session is valid (403 here => bad admin creds)
    for u in _open('GET', '/api/users').get('data', []):
        if u.get('username') == API_USERNAME:
            _open('DELETE', f'/api/users/{u["id"]}')

    created = _open('POST', '/api/users', body={
        'username': API_USERNAME,
        'name': 'Monk API',
        'type': 'api',
        'user_role_id': _super_admin_role_id(),
        'status': 'enabled',
    })['data']
    token = created['password']  # v6 returns the API token here, once

    with open(ENV_LOCAL_PATH, 'w') as fh:
        fh.write(f'LISTMONK_USER={API_USERNAME}\nLISTMONK_TOKEN={token}\n')
    print(f'listmonk-init: wrote LISTMONK_USER/LISTMONK_TOKEN for {API_USERNAME} -> {ENV_LOCAL_PATH}')


if __name__ == '__main__':
    try:
        main()
    except urllib.error.HTTPError as e:
        sys.exit(f'listmonk-init FAILED: HTTP {e.code} {e.read().decode()[:300]}')
    except (urllib.error.URLError, KeyError, OSError) as e:
        sys.exit(f'listmonk-init FAILED: {e}')
