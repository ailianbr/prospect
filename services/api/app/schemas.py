from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

# ---------------------------------------------------------------------------
# Chatwoot campaign body schemas
# Defined here (not in handlers/) to avoid a circular import:
#   app/schemas.py → app/handlers/chatwoot/schemas.py
#   → app/handlers/chatwoot/__init__.py → ChatwootHandler
#   → app/handlers/base.py → app/schemas.py
# ---------------------------------------------------------------------------


class ChatwootButtonParam(BaseModel):
    type: str
    parameter: str  # resolver ref
    url: str
    variables: list[str]


class ChatwootTemplateParams(BaseModel):
    body: dict[str, str]  # slot_id -> resolver ref
    buttons: list[ChatwootButtonParam] = []


class ChatwootTemplateConfig(BaseModel):
    name: str
    language: str
    category: str
    processed_params: ChatwootTemplateParams


class ChatwootCampaignBody(BaseModel):
    content: str
    message_type: str
    private: bool
    content_type: str
    template_params: ChatwootTemplateConfig
    template_id: Optional[str] = None


# =============================================================================
# LISTMONK (LM) SCHEMAS
# Mirror the Listmonk API spec (collections.yaml) exactly.
# =============================================================================


class LM_ListSchema(BaseModel):
    """Listmonk List object — shape returned by GET/POST/PUT /lists."""

    id: int
    created_at: datetime
    updated_at: datetime
    uuid: str
    name: str
    type: Literal['private', 'public']
    optin: Literal['single', 'double']
    tags: List[str]
    description: Optional[str] = None
    status: Optional[str] = None  # present in practice; omitted from the OpenAPI spec
    subscriber_count: int


class LM_CreateListSchema(BaseModel):
    """Listmonk POST /lists request body (NewList spec)."""

    model_config = ConfigDict(
        json_schema_extra={
            'example': {
                'name': 'My Subscribers',
                'type': 'private',
                'optin': 'single',
                'description': 'Main subscriber list',
                'tags': ['newsletter'],
            }
        }
    )

    name: str
    type: Literal['private', 'public'] = 'private'
    optin: Literal['single', 'double']
    tags: Optional[List[str]] = None
    description: Optional[str] = None


class LM_UpdateListSchema(LM_ListSchema):
    """Listmonk PUT /lists/{id} request body — same shape as List, all fields optional."""

    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    uuid: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    optin: Optional[str] = None
    tags: Optional[List[str]] = None
    description: Optional[str] = None
    status: Optional[str] = None
    subscriber_count: Optional[int] = None


class LM_ResponseListSchema(BaseModel):
    """Listmonk single-list response envelope."""

    data: LM_ListSchema


class LM_ResponseListsDataSchema(BaseModel):
    """Inner object of the paginated GET /lists response."""

    results: List[LM_ListSchema]
    total: int
    per_page: int
    page: int


class LM_ResponseListsSchema(BaseModel):
    """Listmonk paginated GET /lists response envelope."""

    data: LM_ResponseListsDataSchema


class LM_CreateCampaignSchema(BaseModel):
    """Listmonk POST /campaigns request body (CampaignRequest spec)."""

    model_config = ConfigDict(
        json_schema_extra={
            'examples': [
                {
                    'summary': 'Email campaign',
                    'value': {
                        'name': 'Welcome Campaign',
                        'subject': 'Welcome to our newsletter!',
                        'lists': [1],
                        'from_email': 'sender@example.com',
                        'type': 'regular',
                        'content_type': 'richtext',
                        'body': '<p>Hello, welcome!</p>',
                        'messenger': 'email',
                    },
                },
                {
                    'summary': 'WhatsApp template campaign',
                    'value': {
                        'name': 'Follow-up Campaign',
                        'subject': 'Follow-up',
                        'lists': [1],
                        'type': 'regular',
                        'content_type': 'plain',
                        'messenger': 'whatsapp',
                        'template_id': '891688563679173',
                        'body': {
                            'content': 'Oi, {{1}}! Tudo certo com o uso do {{2}}?',
                            'message_type': 'outgoing',
                            'private': False,
                            'content_type': 'text',
                            'template_params': {
                                'name': 'follow_2',
                                'category': 'MARKETING',
                                'language': 'pt_BR',
                                'processed_params': {
                                    'body': {
                                        '1': 'lead.name:amigo',
                                        '2': 'instancia.razao_social:nossa empresa',
                                    },
                                },
                            },
                        },
                    },
                },
            ]
        }
    )

    name: str = Field(..., description='Campaign name')
    subject: str = Field(..., description='Campaign email subject')
    lists: List[int] = Field(..., min_length=1, description='List IDs to send campaign to')
    from_email: Optional[str] = Field(None, description="'From' email in campaign emails")
    type: Literal['regular', 'optin'] = Field('regular', description='Campaign type')
    content_type: Literal['richtext', 'html', 'markdown', 'plain'] = Field(..., description='Content type')
    body: Union[str, ChatwootCampaignBody] = Field(..., description='Content body of campaign')
    altbody: Optional[str] = Field(None, description='Alternate plain text body for HTML or richtext emails')
    send_at: Optional[datetime] = Field(None, description='Schedule timestamp (ISO 8601)')
    send_later: Optional[bool] = Field(None, description='Schedule for later')
    messenger: Optional[str] = Field('email', description="Messenger type, defaults to 'email'")
    template_id: Optional[str] = Field(None, description='WhatsApp template ID (string); not forwarded to Listmonk')
    tags: Optional[List[str]] = Field(None, description='Tags to mark campaign')
    headers: Optional[List[Dict[str, str]]] = Field(None, description='SMTP headers as key-value pairs')


class LM_CampaignSchema(BaseModel):
    """Listmonk Campaign object — shape returned by GET/POST /campaigns."""

    id: int
    created_at: datetime
    updated_at: datetime
    uuid: str
    name: str
    subject: str
    from_email: str
    type: Literal['regular', 'optin']
    content_type: Literal['richtext', 'html', 'markdown', 'plain', 'visual']
    status: str
    body: Optional[str] = None
    altbody: Optional[str] = None
    send_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    to_send: int
    sent: int
    views: int
    clicks: int
    messenger: str
    template_id: Optional[int] = None
    tags: Optional[List[str]] = None
    lists: List[Dict[str, Any]]
    headers: Optional[List[Dict[str, str]]] = None
    archive: Optional[bool] = None
    archive_template_id: Optional[int] = None
    archive_meta: Optional[Dict[str, Any]] = None


# =============================================================================
# POCKETBASE (PB) SCHEMAS
# Mirror the PocketBase collection schemas from pb_schema.json.
# =============================================================================


class PB_MonkListSchema(BaseModel):
    """PocketBase monk_lists record."""

    id: str
    created: datetime
    updated: datetime


class PB_MonkClientListSchema(BaseModel):
    """PocketBase monk_client_lists record."""

    id: str
    client: str
    lists: List[str]  # list of monk_list IDs
    default_list: Optional[str] = None
    created: datetime
    updated: datetime


# =============================================================================
# INTERFACE SCHEMAS
# What our API exposes. These are the "pedal" — they abstract over LM and PB.
# Every request carries the client context. The service payload is nested under
# its resource name so each schema is self-contained and unambiguous.
# =============================================================================


class ClientSchema(BaseModel):
    """The client making the request."""

    id: str


class ListSchema(LM_ListSchema):
    """Our API's list response object."""

    pass


class CreateListSchema(BaseModel):
    """Request to create a list."""

    client: ClientSchema
    list: LM_CreateListSchema


class UpdateListSchema(BaseModel):
    """Request to partially update a list."""

    client: ClientSchema
    list: LM_UpdateListSchema


class DeleteListSchema(BaseModel):
    """Request to delete one or more lists."""

    client: ClientSchema
    id: Optional[List[int]] = None
    query: Optional[str] = None

    @model_validator(mode='after')
    def validate_id_or_query(self):
        if not self.id and not self.query:
            raise ValueError("Either 'id' or 'query' must be provided")
        if self.id and self.query:
            raise ValueError("Provide only one of 'id' or 'query', not both")
        return self


class ResponseUpdateListSchema(BaseModel):
    """Response schema for list update operations."""

    data: ListSchema


class DeleteResponseSchema(BaseModel):
    """Response schema for delete operations."""

    data: bool


class LM_UpdateCampaignSchema(LM_CampaignSchema):
    """Listmonk PUT /campaigns/{id} — all fields optional."""

    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    uuid: Optional[str] = None
    name: Optional[str] = None
    subject: Optional[str] = None
    from_email: Optional[str] = None
    type: Optional[str] = None
    content_type: Optional[str] = None
    status: Optional[str] = None
    body: Optional[str] = None
    to_send: Optional[int] = None
    sent: Optional[int] = None
    views: Optional[int] = None
    clicks: Optional[int] = None
    messenger: Optional[str] = None
    lists: Optional[List[Dict[str, Any]]] = None


class CreateCampaignSchema(BaseModel):
    """Request to create a campaign."""

    client: ClientSchema
    campaign: LM_CreateCampaignSchema


class CampaignSchema(LM_CampaignSchema):
    """Our API's campaign response object."""

    pass


class UpdateCampaignSchema(BaseModel):
    """Request to partially update a campaign."""

    client: ClientSchema
    campaign: LM_UpdateCampaignSchema


class ResponseCampaignSchema(BaseModel):
    """Response schema for campaign create/update operations."""

    data: CampaignSchema


# =============================================================================
# CLIENT SCHEMAS
# =============================================================================


class ClientInfoSchema(BaseModel):
    """Client record — ownership info returned by GET /v1/client."""

    id: str
    default_list: Optional[int] = None
    lists: List[int]


# =============================================================================
# SUBSCRIBER IMPORT SCHEMAS
# =============================================================================


class ImportSubscriberItem(BaseModel):
    """A single subscriber entry for JSON bulk import."""

    model_config = ConfigDict(
        json_schema_extra={
            'example': {
                'email': 'subscriber@example.com',
                'name': 'Jane Doe',
            }
        }
    )

    email: EmailStr
    name: str = ''
    attribs: Dict[str, Any] = {}


# =============================================================================
# SUBSCRIBER CRUD SCHEMAS
# =============================================================================


class LM_SubscriberListMembership(BaseModel):
    """Compact list reference embedded inside a Listmonk subscriber object."""

    id: int
    name: str
    type: str
    optin: str
    tags: Optional[List[str]] = None
    description: Optional[str] = None
    subscription_status: Optional[str] = None
    subscription_created_at: Optional[datetime] = None
    subscription_updated_at: Optional[datetime] = None


class LM_SubscriberSchema(BaseModel):
    """Listmonk subscriber object returned by GET/POST/PUT /subscribers."""

    id: int
    created_at: datetime
    updated_at: datetime
    uuid: str
    email: str
    name: str
    status: str
    attribs: Dict[str, Any] = {}
    lists: List[LM_SubscriberListMembership] = []


class LM_CreateSubscriberSchema(BaseModel):
    """Request body for creating a single subscriber."""

    email: EmailStr
    name: str
    status: Literal['enabled', 'disabled', 'blocklisted'] = 'enabled'
    lists: List[int] = []
    attribs: Dict[str, Any] = {}
    preconfirm_subscriptions: bool = True


class LM_UpdateSubscriberSchema(BaseModel):
    """Partial update for a subscriber — omitted fields are preserved."""

    email: Optional[EmailStr] = None
    name: Optional[str] = None
    status: Optional[Literal['enabled', 'disabled', 'blocklisted']] = None
    attribs: Optional[Dict[str, Any]] = None
    lists: Optional[List[int]] = None


class LM_ResponseSubscribersDataSchema(BaseModel):
    """Inner paginated result for GET /subscribers."""

    results: Optional[List[LM_SubscriberSchema]] = None  # Listmonk returns null when empty
    total: int
    per_page: int
    page: int


class ResponseSubscriberSchema(BaseModel):
    """Single-subscriber response envelope."""

    data: LM_SubscriberSchema


class ResponseSubscribersSchema(BaseModel):
    """Paginated subscriber list response envelope."""

    data: LM_ResponseSubscribersDataSchema


# =============================================================================
# MESSENGER SCHEMAS
# Shape of the payload Listmonk sends to a custom messenger endpoint.
# =============================================================================


class MessengerAttachment(BaseModel):
    url: str
    name: str


class MessengerRecipient(BaseModel):
    uuid: str
    email: str
    name: str
    attribs: Dict[str, Any] = {}
    status: str


class MessengerCampaignMeta(BaseModel):
    uuid: str
    name: str
    tags: Optional[List[str]] = None


class MessengerPayload(BaseModel):
    subject: str
    body: str
    content_type: str
    recipients: List[MessengerRecipient]
    campaign: MessengerCampaignMeta
    attachments: Optional[List[MessengerAttachment]] = None
