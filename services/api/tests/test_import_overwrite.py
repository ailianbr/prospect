# tests/test_import_overwrite.py
"""Unit test for the opt-in `overwrite` import flag — fully mocked (no live Listmonk/PocketBase),
so it can run without Doppler-injected credentials."""

import json
from unittest.mock import MagicMock

from app.interface import Interface, interface
from app.schemas import ClientSchema, ImportSubscriberItem


def test_import_overwrite_forwarded_to_listmonk(monkeypatch):
    """`overwrite` reaches Listmonk's import params (default false) so a re-import can update an
    existing subscriber's attribs only when explicitly asked to."""
    captured: dict = {}
    monkeypatch.setattr(Interface, '_resolve_target_list', lambda self, client, list_id: 7)

    def fake_multipart(files, data, path=None):
        captured['params'] = json.loads(data['params'])
        resp = MagicMock(ok=True)
        resp.json.return_value = {'data': True}
        return resp

    monkeypatch.setattr(interface._Interface__monk_subscribers, 'post_multipart', fake_multipart)
    items = [ImportSubscriberItem(email='a@b.com', name='A', attribs={'phone': '+55'})]

    interface.import_subscribers_json(ClientSchema(id='mxf'), items, overwrite=True)
    assert captured['params']['overwrite'] is True
    assert captured['params']['lists'] == [7]

    interface.import_subscribers_json(ClientSchema(id='mxf'), items)
    assert captured['params']['overwrite'] is False
