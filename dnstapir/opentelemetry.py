import logging

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from pydantic import AnyHttpUrl, BaseModel

logger = logging.getLogger(__name__)

DEFAULT_OTLP_SERVICE_NAME = "dnstapir"


class OtlpSettings(BaseModel):
    service_name: str | None = None
    spans_endpoint: AnyHttpUrl | None = None
    metrics_endpoint: AnyHttpUrl | None = None
    insecure: bool = False


def configure_opentelemetry(
    settings: OtlpSettings,
    service_name: str | None = None,
    fastapi_app: FastAPI | None = None,
) -> None:
    service_name = settings.service_name or service_name or DEFAULT_OTLP_SERVICE_NAME
    resource = Resource(attributes={SERVICE_NAME: service_name})

    trace_provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(
        OTLPSpanExporter(endpoint=settings.spans_endpoint, insecure=settings.insecure)
        if settings.spans_endpoint
        else ConsoleSpanExporter()
    )
    trace_provider.add_span_processor(processor)
    trace.set_tracer_provider(trace_provider)
    logger.debug("OTLP spans via %s", settings.spans_endpoint or "console")

    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=settings.metrics_endpoint, insecure=settings.insecure)
        if settings.metrics_endpoint
        else ConsoleMetricExporter()
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)
    logger.debug("OTLP metrics via %s", settings.metrics_endpoint or "console")

    if fastapi_app:
        FastAPIInstrumentor.instrument_app(
            app=fastapi_app,
            http_capture_headers_server_request=[
                "x-request-id",
                "traceparent",
                "tracestate",
            ],
        )
    PymongoInstrumentor().instrument()
    BotocoreInstrumentor().instrument()
    RedisInstrumentor().instrument()

    logger.info("OpenTelemetry configured")
