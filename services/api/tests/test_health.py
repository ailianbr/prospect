# tests/test_health.py
"""The unauthenticated /health probe used for uptime checks and deploy verification."""

from http import HTTPStatus


def test_health(client):
    response = client.get('/health')
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body['status'] == 'ok'
    assert body['service'] == 'monk-api'
    assert body['version']
    assert body['environment']
