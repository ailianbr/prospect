from dataclasses import dataclass
from http import HTTPStatus
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, UploadFile

from app.interface import Interface, get_interface_api
from app.schemas import (
    ClientSchema,
    ImportSubscriberItem,
    LM_CreateSubscriberSchema,
    LM_UpdateSubscriberSchema,
    ResponseSubscriberSchema,
    ResponseSubscribersSchema,
)

router = APIRouter(
    prefix='/subscriber',
    responses={404: {'description': 'Not found'}},
)

Api = Annotated[Interface, Depends(get_interface_api)]
InstanceID = Annotated[str, Header()]


@dataclass
class _ListSubscribersQuery:
    list_id: Optional[int] = None
    page: int = 1
    per_page: int = 20
    query: Optional[str] = None


ListSubscribersQuery = Annotated[_ListSubscribersQuery, Depends()]


@router.post('/import', status_code=HTTPStatus.OK)
async def import_subscribers(
    file: UploadFile, api: Api, x_instance_id: InstanceID, list_id: Optional[int] = None, overwrite: bool = False
):
    """Upload a CSV of subscribers and enroll them in the specified list (or the client's default list).

    `overwrite=true` updates subscribers that already exist (name/attribs); by default existing
    subscribers are left untouched and only new ones are created.
    """
    content = await file.read()
    return api.import_subscribers(ClientSchema(id=x_instance_id), content, file.filename, list_id, overwrite)


@router.post('/import/json', status_code=HTTPStatus.OK)
def import_subscribers_json(
    body: list[ImportSubscriberItem],
    api: Api,
    x_instance_id: InstanceID,
    list_id: Optional[int] = None,
    overwrite: bool = False,
):
    """Upload a JSON array of subscribers and enroll them in the specified list (or the client's default list).

    `overwrite=true` updates subscribers that already exist (name/attribs); by default existing
    subscribers are left untouched and only new ones are created.
    """
    return api.import_subscribers_json(ClientSchema(id=x_instance_id), body, list_id, overwrite)


@router.get('', response_model=ResponseSubscribersSchema)
def list_subscribers(api: Api, x_instance_id: InstanceID, params: ListSubscribersQuery):
    """List subscribers scoped to a client's list.

    If `list_id` is provided it must belong to the client. If omitted, the
    client's default list is used. Supports `page`/`per_page` pagination and
    an optional Listmonk SQL-like `query` filter.
    """
    return api.get_subscribers(ClientSchema(id=x_instance_id), params.list_id, params.page, params.per_page, params.query)


@router.get('/{subscriber_id}', response_model=ResponseSubscriberSchema)
def get_subscriber(subscriber_id: int, api: Api, x_instance_id: InstanceID):
    """Get a single subscriber by Listmonk ID.

    Returns 403 if the subscriber does not belong to any of the client's lists.
    """
    return api.get_subscriber(subscriber_id, ClientSchema(id=x_instance_id))


@router.post('', status_code=HTTPStatus.CREATED, response_model=ResponseSubscriberSchema)
def create_subscriber(body: LM_CreateSubscriberSchema, api: Api, x_instance_id: InstanceID):
    """Create a single subscriber.

    If `lists` is empty or omitted, the subscriber is enrolled in the client's
    default list. Any `lists` provided must belong to the client.
    Returns 409 if a subscriber with this email already exists.
    """
    return api.create_subscriber(ClientSchema(id=x_instance_id), body)


@router.put('/{subscriber_id}', response_model=ResponseSubscriberSchema)
def update_subscriber(subscriber_id: int, body: LM_UpdateSubscriberSchema, api: Api, x_instance_id: InstanceID):
    """Partially update a subscriber's name, email, status, or attribs.

    Fields omitted from the request body are preserved. If `lists` is provided,
    all list IDs must belong to the client.
    Returns 403 if the subscriber does not belong to any of the client's lists.
    """
    return api.update_subscriber(subscriber_id, ClientSchema(id=x_instance_id), body)


@router.delete('/{subscriber_id}')
def delete_subscriber(
    subscriber_id: int,
    api: Api,
    x_instance_id: InstanceID,
    list_id: Optional[int] = None,
):
    """Delete or unsubscribe a subscriber.

    - No `list_id` (or `list_id` equals the client's default list): permanently
      deletes the subscriber from Listmonk.
    - Non-default `list_id`: removes the subscriber from that list only.

    Returns 403 if the subscriber does not belong to any of the client's lists.
    """
    return api.delete_subscriber(subscriber_id, ClientSchema(id=x_instance_id), list_id)
