# app/sessions.py
import base64
import json
import logging
import secrets
import time
from dataclasses import dataclass

import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pocketbase import PocketBase
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.context import enrich_wide_event
from app.settings import settings

logger = logging.getLogger(__name__)

pb_client = PocketBase(settings.POCKETBASE_API_URL)

security = HTTPBasic()

_EXPIRY_THRESHOLD = 300  # re-auth if token expires within 5 minutes


def _token_exp(token: str) -> float:
    """Decode JWT exp claim without verifying signature."""
    try:
        payload_b64 = token.split('.')[1]
        payload_b64 += '=' * (-len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(payload_b64))
        return float(payload.get('exp', 0))
    except Exception:
        return 0.0


def _ensure_pb_auth() -> None:
    """Authenticate the PB client when needed.

    Called lazily by PocketBaseSession (the first request that needs PocketBase),
    never at import — so importing the app does no network I/O and can run without
    a live PocketBase (tests, alembic, CLI tools).
    """
    token = pb_client.auth_store.token
    if not token or time.time() >= (_token_exp(token) - _EXPIRY_THRESHOLD):
        try:
            pb_client.collection('_superusers').auth_with_password(
                settings.POCKETBASE_BOT_EMAIL, settings.POCKETBASE_BOT_PASSWORD
            )
            logger.info('pocketbase.auth_refreshed')
        except Exception as e:
            logger.error('pocketbase.auth_failed', extra={'error': str(e)})
            raise HTTPException(status_code=503, detail=f'PocketBase auth failed: {e}')


@dataclass
class MonkSession:
    username: str


def get_monk_session(
    credentials: HTTPBasicCredentials = Depends(security),
) -> MonkSession:
    if not (
        secrets.compare_digest(credentials.username, settings.LISTMONK_USER)
        and secrets.compare_digest(credentials.password, settings.LISTMONK_TOKEN)
    ):
        enrich_wide_event({'auth': {'outcome': 'invalid_credentials', 'username': credentials.username}})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid authentication credentials',
            headers={'WWW-Authenticate': 'Basic'},
        )

    return MonkSession(username=credentials.username)


class PocketBaseSession:
    @property
    def client(self) -> PocketBase:
        # Lazily authenticate on first use so constructing the session — including
        # the module-level `interface` in interface.py — does no network I/O at import.
        _ensure_pb_auth()
        return pb_client


def get_pocketbase_session() -> PocketBaseSession:
    return PocketBaseSession()


class Monk:
    _MAX_RETRIES = 3
    _BACKOFF_FACTOR = 1  # delays: 1s, 2s, 4s

    def __init__(self, auth_creds, url, timeout=5):
        self.__url = url
        self.timeout = timeout

        retry = Retry(
            total=self._MAX_RETRIES,
            backoff_factor=self._BACKOFF_FACTOR,
            allowed_methods=False,  # retry all HTTP methods
            status_forcelist=[],  # only retry on network/timeout errors, not HTTP errors
        )
        self.__session = requests.Session()
        self.__session.mount('http://', HTTPAdapter(max_retries=retry))
        self.__session.mount('https://', HTTPAdapter(max_retries=retry))
        self.__session.auth = auth_creds

    def delete(self, params, path=None):
        url = self.__url + path if path else self.__url
        return self.__session.delete(url, params=params, timeout=self.timeout)

    def post(self, params, path=None):
        url = self.__url + path if path else self.__url
        return self.__session.post(url, json=params, timeout=self.timeout)

    def post_multipart(self, files, data, path=None):
        url = self.__url + path if path else self.__url
        return self.__session.post(url, files=files, data=data, timeout=self.timeout)

    def put(self, params, path=None):
        url = self.__url + path if path else self.__url
        return self.__session.put(url, json=params, timeout=self.timeout)

    def patch(self, params):
        return self.__session.patch(self.__url, params=params, timeout=self.timeout)

    def get(self, params, path=None):
        url = self.__url + path if path else self.__url
        return self.__session.get(url, params=params, timeout=self.timeout)
