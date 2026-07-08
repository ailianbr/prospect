# API Best Practices

Patterns and conventions adopted in this service to keep the codebase reliable, maintainable, and secure.

---

## Testing

### Integration tests over unit tests
Tests hit live Listmonk and PocketBase instances (injected via Doppler). Mocks are avoided because they hide real-world divergences — a mock that passes does not mean the integration works.

### Schema contract tests
`tests/test_schema_contracts.py` fetches every campaign and list from the live Listmonk instance at test-collection time and tries to parse each one through the corresponding Pydantic schema. This catches enum mismatches, undocumented field values, and nullable surprises before they reach production.

```python
@pytest.mark.parametrize('campaign', _fetch_all_campaigns(), ids=lambda c: f"campaign_{c['id']}")
def test_campaign_schema_parses_listmonk_response(campaign):
    CampaignSchema(**campaign)
```

Any time Listmonk stores a value outside our schema (e.g. a new `content_type`), the test fails with the exact record ID as the test name.

### End-to-end tests
`tests/test_e2e.py` covers the full client lifecycle in a single test: import subscriber (auto-creates client + default list) → create campaign → start campaign. This ensures all layers work together, not just individually.

### CI validation before commit
Every workflow change is validated locally with `act` before committing:

```bash
act pull_request --job test -W .github/workflows/ci.yml -n   # dry-run
doppler run -c stg_act -- sh -c 'act pull_request --job test ...'  # real run
```

---

## Schema Design

### Mirror the upstream spec, validate with Literals
Schemas in `schemas.py` mirror the Listmonk OpenAPI spec (`services/listmonk/collections.yaml`). Fields with known enum values use `Literal` instead of `str` so invalid values are rejected at the boundary:

```python
type: Literal['regular', 'optin']
content_type: Literal['richtext', 'html', 'markdown', 'plain', 'visual']
```

The contract tests ensure these enums stay in sync with what Listmonk actually returns.

### Datetime serialization
When passing Pydantic models to `requests`, always use `model_dump(mode='json')` so that `datetime` fields are serialized to ISO 8601 strings. Plain `model_dump()` returns Python objects that `json.dumps` cannot serialize:

```python
# Wrong — datetime object causes TypeError
response = self.__monk_campaigns.post(payload.campaign.model_dump())

# Correct
response = self.__monk_campaigns.post(payload.campaign.model_dump(mode='json'))
```

### Swagger examples
Request schemas include a `model_config` with a realistic example so the Swagger UI shows a copy-pasteable payload instead of generic `"string"` / `0` placeholders:

```python
model_config = ConfigDict(json_schema_extra={'example': {
    'name': 'Welcome Campaign',
    'lists': [1],          # replace with a real list ID
    'type': 'regular',
    ...
}})
```

---

## Error Handling

### Forward upstream errors
Every Listmonk response is checked through `_raise_for_listmonk()` instead of bare `raise_for_status()`. This converts Listmonk 4xx responses into `HTTPException` with the original message and status code rather than an unhandled 500:

```python
@staticmethod
def _raise_for_listmonk(response: requests.Response) -> None:
    if response.ok:
        return
    try:
        detail = response.json().get('message', response.text)
    except Exception:
        detail = response.text
    raise HTTPException(status_code=response.status_code, detail=detail)
```

### Environment-aware unhandled exceptions
Any exception that reaches FastAPI's global handler is treated differently based on the `ENVIRONMENT` setting:

| `ENVIRONMENT` | Response | Side effect |
|---------------|----------|-------------|
| `DEV` | `500` with full error message and traceback | — |
| `PRD` (default) | `401 Unauthorized` | Error logged with full context |

This prevents internal stack traces from leaking in production while keeping them visible during development.

---

## API Design

### Unknown clients return empty, not 404
`GET` endpoints that list resources return `[]` for unregistered clients instead of 404. The client ID is an opaque token — a 404 would reveal whether an ID is registered. New clients are auto-provisioned on first subscriber import.

### Ownership enforced at the interface layer
All ownership checks (does this list/campaign belong to this client?) happen in `Interface` (`app/interface.py`), not in routers. Routers are thin — they extract the `X-Instance-ID` header, build the payload, and delegate everything else.

### No authentication middleware
Endpoints are identified by the `X-Instance-ID` header. There is no HTTP Basic Auth on any endpoint. Authentication is a concern of the upstream proxy, not this service.

### No trailing slash on root collection endpoints
Root collection routes are registered without a trailing slash (e.g. `GET /v1/campaign`, `POST /v1/list`). Using `'/'` as the route path causes FastAPI to issue a 307 redirect for requests without the slash — HTTP clients that do not follow redirects by default (e.g. `curl`) will silently fail. Parameterised sub-routes (e.g. `/{id}/start`) are unaffected.

---

## Secrets & Environment

All environment variables are managed via **Doppler**. Every command that needs secrets is prefixed:

```bash
doppler run -- <command>
```

Doppler config branches used:

| Config | Purpose |
|--------|---------|
| `dev_local_test` | Local development — hits local Docker services |
| `dev_personal` | Local development — hits services via devtunnels |
| `stg_act` | Local `act` runs — hits staging, mocks deploy webhook |
| `stg` | Staging environment |
| `prd` | Production environment |

---

## Git Workflow

### Commit convention
All commits follow the Commitizen convention: `<type>(<scope>): <subject>`.

Common types: `feat`, `fix`, `test`, `refactor`, `ci`, `chore`, `docs`.

### Branch flow
```
feature branch → development (PR)
development    → main (PR, triggers CI)
main merge     → release-please (automated release PR)
release PR     → production deploy
```

### CI cascade
Jobs in `deploy-stg.yml` run sequentially: `lint → test → deploy`. There is no reason to deploy if tests fail, and no reason to test if lint fails.
