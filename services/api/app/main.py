import traceback
from importlib.metadata import version  # stdlib — reads version from pyproject.toml at runtime

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from scalar_fastapi import get_scalar_api_reference

from .context import enrich_wide_event
from .logging_config import configure_logging
from .middleware import WideEventMiddleware
from .routers import campaign, channels, client, leads, lists, messenger
from .settings import settings
from .telemetry import configure_telemetry

configure_logging()

app = FastAPI(version=version('listmonk'), docs_url=None, redoc_url=None)

app.add_middleware(WideEventMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Must be called after middleware is registered: instrument_app() adds its own
# middleware and must be outermost so spans are active when WideEventMiddleware logs.
configure_telemetry(app)


@app.get('/docs', include_in_schema=False)
async def scalar_docs():
    return get_scalar_api_reference(openapi_url=app.openapi_url, title=app.title)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    enrich_wide_event({'error': {'type': type(exc).__name__, 'message': str(exc)}})
    if settings.is_dev:
        return JSONResponse(
            status_code=500,
            content={'detail': str(exc), 'traceback': traceback.format_exc()},
        )
    return JSONResponse(status_code=401, content={'detail': 'Unauthorized'})


v1 = APIRouter(prefix='/v1')
v1.include_router(client.router)
v1.include_router(lists.router)
v1.include_router(campaign.router)
v1.include_router(leads.router)
v1.include_router(messenger.router)
v1.include_router(channels.router)

app.include_router(v1)
app.include_router(v1, prefix='/api')
