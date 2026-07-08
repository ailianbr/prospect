# tests/conftest.py
import pytest
from fastapi.testclient import TestClient

from app.handlers.fake import FakeHandler
from app.interface import interface
from app.main import app
from app.schemas import (
    ClientSchema,
    CreateCampaignSchema,
    CreateListSchema,
    DeleteListSchema,
    LM_CreateCampaignSchema,
    LM_CreateListSchema,
)
from app.sessions import MonkSession, get_monk_session
from app.settings import settings


@pytest.fixture(autouse=True)
def clear_fake_handler():
    FakeHandler.received.clear()


@pytest.fixture(scope='session')
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def override_monk():
    def fake_monk():
        return MonkSession(username=settings.LISTMONK_USER)

    app.dependency_overrides[get_monk_session] = fake_monk
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def list_payload():
    return {
        'name': 'Automated Test',
        'type': 'public',
        'optin': 'double',
        'tags': ['marketing', 'email'],
        'description': 'Automatic generated List',
    }


@pytest.fixture
def created_list(list_payload):
    payload = CreateListSchema(
        client=ClientSchema(id='mxf'),
        list=LM_CreateListSchema(**list_payload),
    )
    list_obj = interface.create_list(payload)
    yield list_obj.model_dump()
    interface.delete_list(DeleteListSchema(client=ClientSchema(id='mxf'), id=[list_obj.id]))


@pytest.fixture
def campaign_payload(created_list):
    return {
        'name': 'Automated Campaign Test',
        'subject': 'Test Subject',
        'lists': [created_list['id']],
        'type': 'regular',
        'content_type': 'plain',
        'body': 'Hello, this is a test campaign.',
    }


@pytest.fixture
def created_campaign(campaign_payload):
    payload = CreateCampaignSchema(
        client=ClientSchema(id='mxf'),
        campaign=LM_CreateCampaignSchema(**campaign_payload),
    )
    campaign_obj = interface.create_campaign(payload)
    yield campaign_obj.model_dump()
    interface.delete_campaign(campaign_obj.id, ClientSchema(id='mxf'))
