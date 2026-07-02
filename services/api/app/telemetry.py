import logging

from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .context import ENV_CONTEXT
from .settings import Settings

logger = logging.getLogger(__name__)


def configure_telemetry(app) -> None:
    """Wire OpenTelemetry tracing when OTEL_EXPORTER_OTLP_ENDPOINT is set.

    No-op when the env var is absent; the app runs without tracing.

    When enabled:
    - TracerProvider exports spans via OTLP/gRPC
    - FastAPIInstrumentor creates a root span per HTTP request
    - RequestsInstrumentor creates child spans for outbound Listmonk calls
    - LoggingInstrumentor injects otelTraceID / otelSpanID / otelServiceName
      into every LogRecord; _JSONFormatter picks these up automatically so
      wide events are correlated with traces without any call-site changes
    """
    # Read at call time (once, at startup) via a fresh Settings() so the endpoint
    # reflects the environment when telemetry is configured.
    endpoint = Settings().OTEL_EXPORTER_OTLP_ENDPOINT
    if not endpoint:
        return

    # Derived from ENV_CONTEXT so OTel spans carry identical metadata to wide events.
    # service.instance.id and service.commit are OTel semantic conventions for the
    # fields already present in every wide event as instance_id and commit_sha.
    resource = Resource.create({
        'service.name': ENV_CONTEXT['service'],
        'service.version': ENV_CONTEXT['version'],
        'deployment.environment': ENV_CONTEXT['environment'],
        'service.instance.id': ENV_CONTEXT['instance_id'],
        'service.commit': ENV_CONTEXT['commit_sha'],
    })

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)

    log_provider = LoggerProvider(resource=resource)
    log_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint)))
    set_logger_provider(log_provider)
    logging.getLogger().addHandler(LoggingHandler(logger_provider=log_provider))

    # Instrument outbound HTTP calls first so child spans are created for every
    # requests.Session call made by the Monk HTTP client.
    RequestsInstrumentor().instrument()

    # set_logging_format=False: keep our _JSONFormatter; OTel still injects
    # otelTraceID / otelSpanID / otelServiceName / otelTraceSampled into every
    # LogRecord via the record factory — these surface in JSON output for free.
    LoggingInstrumentor().instrument(set_logging_format=False)

    # Must come last: instrument_app() adds OpenTelemetryMiddleware which
    # becomes the outermost middleware, ensuring spans are active before
    # WideEventMiddleware logs.
    FastAPIInstrumentor.instrument_app(app)

    logger.info('telemetry.configured', extra={'endpoint': endpoint})
