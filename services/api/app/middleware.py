import logging
import time
import uuid
from typing import override

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .context import ENV_CONTEXT, set_wide_event

logger = logging.getLogger(__name__)


class WideEventMiddleware(BaseHTTPMiddleware):
    """Emit one structured wide event per request.

    Initialises the wide event with HTTP and environment context, exposes it via
    a ContextVar so handlers can enrich it with business context, then emits a
    single JSON log line in the finally block.  INFO on success (< 400),
    ERROR on failure (>= 400).
    """

    _ERROR_THRESHOLD = 400

    @override
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get('x-request-id') or str(uuid.uuid4())
        start = time.monotonic()

        wide_event: dict = {
            'request_id': request_id,
            'method': request.method,
            'path': request.url.path,
            'user_agent': request.headers.get('user-agent'),
            **ENV_CONTEXT,
        }
        if instance_id := request.headers.get('x-instance-id'):
            wide_event['client_id'] = instance_id
        set_wide_event(wide_event)

        try:
            response = await call_next(request)
            wide_event['status_code'] = response.status_code
            wide_event['outcome'] = 'success' if response.status_code < self._ERROR_THRESHOLD else 'error'
        except Exception as exc:
            wide_event['status_code'] = 500
            wide_event['outcome'] = 'error'
            wide_event.setdefault('error', {'type': type(exc).__name__, 'message': str(exc)})
            raise
        finally:
            wide_event['duration_ms'] = round((time.monotonic() - start) * 1000, 1)
            level = logging.ERROR if wide_event.get('outcome') == 'error' else logging.INFO
            if wide_event.get('outcome') == 'error':
                error = wide_event.get('error', {})
                msg = error.get('message') or f'request failed with {wide_event.get("status_code")}'
            else:
                msg = 'request'
            logger.log(level, msg, extra=wide_event)

        response.headers['x-request-id'] = request_id
        return response
