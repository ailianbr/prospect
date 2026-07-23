import csv
import io
import json
from http import HTTPStatus

import pytest

from app.interface import Interface, interface
from app.schemas import (
    ClientSchema,
    CreateListSchema,
    DeleteListSchema,
    LM_CreateListSchema,
    LM_CreateSubscriberSchema,
    LM_UpdateSubscriberSchema,
)

TEST_EMAIL = 'testimport@example.com'

MXF = {'X-Instance-ID': 'mxf'}
OTHER = {'X-Instance-ID': 'other_test_client'}
NEW_CLIENT = 'brand-new-client'
NEW_CLIENT_HDR = {'X-Instance-ID': NEW_CLIENT}


@pytest.fixture
def cleanup_new_client():
    yield
    try:
        info = interface.get_client(ClientSchema(id=NEW_CLIENT))
        if info.lists:
            interface.delete_list(DeleteListSchema(client=ClientSchema(id=NEW_CLIENT), id=info.lists))
    except Exception:
        pass


@pytest.fixture(autouse=True)
def cleanup_test_subscriber():
    yield
    interface.delete_subscriber_by_email(TEST_EMAIL)


def test_import_to_default_list(client, created_list):
    """Import without list_id enrolls subscribers in the client's default list."""
    csv_content = f'email,name\n{TEST_EMAIL},Test User\n'.encode()
    response = client.post(
        '/v1/subscriber/import',
        files={'file': ('subscribers.csv', io.BytesIO(csv_content), 'text/csv')},
        headers=MXF,
    )
    assert response.status_code == HTTPStatus.OK


def test_import_to_specific_list(client, created_list):
    """Import with a valid list_id owned by the client enrolls in that list."""
    csv_content = f'email,name\n{TEST_EMAIL},Test User\n'.encode()
    response = client.post(
        f'/v1/subscriber/import?list_id={created_list["id"]}',
        files={'file': ('subscribers.csv', io.BytesIO(csv_content), 'text/csv')},
        headers=MXF,
    )
    assert response.status_code == HTTPStatus.OK


def test_import_with_invalid_list_returns_404(client, created_list):
    """Import with a list_id not owned by the client returns 404."""
    csv_content = f'email,name\n{TEST_EMAIL},Test User\n'.encode()
    response = client.post(
        '/v1/subscriber/import?list_id=99999',
        files={'file': ('subscribers.csv', io.BytesIO(csv_content), 'text/csv')},
        headers=MXF,
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_json_import_to_default_list(client, created_list):
    """JSON import without list_id enrolls subscribers in the client's default list."""
    response = client.post(
        '/v1/subscriber/import/json',
        json=[{'email': TEST_EMAIL, 'name': 'Test User'}],
        headers=MXF,
    )
    assert response.status_code == HTTPStatus.OK


def test_json_import_to_specific_list(client, created_list):
    """JSON import with a valid list_id owned by the client enrolls in that list."""
    response = client.post(
        f'/v1/subscriber/import/json?list_id={created_list["id"]}',
        json=[{'email': TEST_EMAIL, 'name': 'Test User'}],
        headers=MXF,
    )
    assert response.status_code == HTTPStatus.OK


def test_json_import_with_invalid_list_returns_404(client, created_list):
    """JSON import with a list_id not owned by the client returns 404."""
    response = client.post(
        '/v1/subscriber/import/json?list_id=99999',
        json=[{'email': TEST_EMAIL, 'name': 'Test User'}],
        headers=MXF,
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_import_auto_creates_client_and_default_list(client, cleanup_new_client):
    """CSV import for an unknown client auto-creates the client with a default list."""
    csv_content = f'email,name\n{TEST_EMAIL},Test User\n'.encode()
    response = client.post(
        '/v1/subscriber/import',
        files={'file': ('subscribers.csv', io.BytesIO(csv_content), 'text/csv')},
        headers=NEW_CLIENT_HDR,
    )
    assert response.status_code == HTTPStatus.OK
    info = interface.get_client(ClientSchema(id=NEW_CLIENT))
    assert info.default_list is not None


def test_json_import_auto_creates_client_and_default_list(client, cleanup_new_client):
    """JSON import for an unknown client auto-creates the client with a default list."""
    response = client.post(
        '/v1/subscriber/import/json',
        json=[{'email': TEST_EMAIL, 'name': 'Test User'}],
        headers=NEW_CLIENT_HDR,
    )
    assert response.status_code == HTTPStatus.OK
    info = interface.get_client(ClientSchema(id=NEW_CLIENT))
    assert info.default_list is not None


def test_json_import_carries_attribs_to_listmonk(client, created_list, monkeypatch):
    """JSON import forwards per-subscriber attribs (e.g. the WhatsApp `phone`) to Listmonk
    as the CSV `attributes` column instead of dropping them."""
    captured: dict = {}

    def fake_post_csv(self, client_arg, file_bytes, filename, target_list):
        captured['bytes'] = file_bytes
        return {'data': True}

    monkeypatch.setattr(Interface, '_post_csv_to_listmonk', fake_post_csv)

    response = client.post(
        f'/v1/subscriber/import/json?list_id={created_list["id"]}',
        json=[{'email': TEST_EMAIL, 'name': 'Test User', 'attribs': {'phone': '+5541999999999'}}],
        headers=MXF,
    )
    assert response.status_code == HTTPStatus.OK

    rows = list(csv.DictReader(io.StringIO(captured['bytes'].decode())))
    assert rows
    assert 'attributes' in rows[0]
    assert json.loads(rows[0]['attributes']) == {'phone': '+5541999999999'}


# =============================================================================
# Subscriber CRUD fixtures & tests
# =============================================================================


@pytest.fixture
def created_subscriber(created_list):
    """Create a subscriber in the mxf client's default list."""
    sub = interface.create_subscriber(
        ClientSchema(id='mxf'),
        LM_CreateSubscriberSchema(email=TEST_EMAIL, name='Test User'),
    )
    return sub.data


def test_list_subscribers_default_list(client, created_subscriber):
    """GET /subscriber returns subscribers from the client's default list."""
    response = client.get('/v1/subscriber', headers=MXF)
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert 'data' in body
    assert isinstance(body['data']['results'], list)


def test_list_subscribers_specific_list(client, created_list, created_subscriber):
    """GET /subscriber?list_id= scoped to a client-owned list."""
    # Import into the specific list first so it appears there
    interface.create_subscriber(
        ClientSchema(id='mxf'),
        LM_CreateSubscriberSchema(email='second_test@example.com', name='Second', lists=[created_list['id']]),
    )
    response = client.get(f'/v1/subscriber?list_id={created_list["id"]}', headers=MXF)
    assert response.status_code == HTTPStatus.OK
    interface.delete_subscriber_by_email('second_test@example.com')


def test_list_subscribers_invalid_list_returns_404(client, created_list):
    """GET /subscriber with a list not owned by the client returns 404."""
    response = client.get('/v1/subscriber?list_id=99999', headers=MXF)
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_get_subscriber(client, created_subscriber):
    """GET /subscriber/{id} returns the subscriber when it belongs to the client."""
    response = client.get(f'/v1/subscriber/{created_subscriber.id}', headers=MXF)
    assert response.status_code == HTTPStatus.OK
    assert response.json()['data']['email'] == TEST_EMAIL


def test_get_subscriber_foreign_returns_403(client, created_subscriber):
    """GET /subscriber/{id} returns 403 when subscriber doesn't belong to requesting client."""
    response = client.get(f'/v1/subscriber/{created_subscriber.id}', headers=OTHER)
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_create_subscriber_to_default_list(client, created_list):
    """POST /subscriber without lists enrolls subscriber in the client's default list."""
    response = client.post(
        '/v1/subscriber',
        json={'email': TEST_EMAIL, 'name': 'Test User'},
        headers=MXF,
    )
    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['data']['email'] == TEST_EMAIL


def test_create_subscriber_to_specific_list(client, created_list):
    """POST /subscriber with a valid list_id enrolls in that list."""
    response = client.post(
        '/v1/subscriber',
        json={'email': TEST_EMAIL, 'name': 'Test User', 'lists': [created_list['id']]},
        headers=MXF,
    )
    assert response.status_code == HTTPStatus.CREATED


def test_create_subscriber_invalid_list_returns_403(client, created_list):
    """POST /subscriber with a list not owned by the client returns 403."""
    response = client.post(
        '/v1/subscriber',
        json={'email': TEST_EMAIL, 'name': 'Test User', 'lists': [99999]},
        headers=MXF,
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_update_subscriber(client, created_subscriber):
    """PUT /subscriber/{id} updates subscriber fields."""
    response = client.put(
        f'/v1/subscriber/{created_subscriber.id}',
        json={'name': 'Updated Name'},
        headers=MXF,
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()['data']['name'] == 'Updated Name'


def test_update_subscriber_foreign_returns_403(client, created_subscriber):
    """PUT /subscriber/{id} returns 403 when subscriber doesn't belong to requesting client."""
    response = client.put(
        f'/v1/subscriber/{created_subscriber.id}',
        json={'name': 'Hacked'},
        headers=OTHER,
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_delete_subscriber_hard(client, created_subscriber):
    """DELETE /subscriber/{id} without list_id permanently removes the subscriber."""
    sub_id = created_subscriber.id
    response = client.delete(f'/v1/subscriber/{sub_id}', headers=MXF)
    assert response.status_code == HTTPStatus.OK
    # Subscriber should be gone — a subsequent GET returns 404
    get_response = client.get(f'/v1/subscriber/{sub_id}', headers=MXF)
    assert get_response.status_code == HTTPStatus.NOT_FOUND


def test_delete_subscriber_soft(client, created_subscriber):
    """DELETE /subscriber/{id}?list_id=X unsubscribes from that list, doesn't hard-delete."""
    # Create a secondary list guaranteed to not be the default (default was already set when
    # created_subscriber was created above).
    secondary = interface.create_list(
        CreateListSchema(
            client=ClientSchema(id='mxf'),
            list=LM_CreateListSchema(name='Soft Delete Test List', type='private', optin='single'),
        )
    )
    try:
        # Enroll subscriber in the secondary list too
        interface.update_subscriber(
            created_subscriber.id,
            ClientSchema(id='mxf'),
            LM_UpdateSubscriberSchema(lists=[*[lst.id for lst in created_subscriber.lists], secondary.id]),
        )
        response = client.delete(
            f'/v1/subscriber/{created_subscriber.id}?list_id={secondary.id}',
            headers=MXF,
        )
        assert response.status_code == HTTPStatus.OK
        # Subscriber should still exist (still in default list)
        get_response = client.get(f'/v1/subscriber/{created_subscriber.id}', headers=MXF)
        assert get_response.status_code == HTTPStatus.OK
    finally:
        interface.delete_list(DeleteListSchema(client=ClientSchema(id='mxf'), id=[secondary.id]))


def test_delete_subscriber_foreign_returns_403(client, created_subscriber):
    """DELETE /subscriber/{id} returns 403 when subscriber doesn't belong to requesting client."""
    response = client.delete(f'/v1/subscriber/{created_subscriber.id}', headers=OTHER)
    assert response.status_code == HTTPStatus.FORBIDDEN
