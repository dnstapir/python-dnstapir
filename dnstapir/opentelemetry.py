import logging
import re
from typing import Annotated, Any

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter as OTLPMetricExporterGrpc
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as OTLPSpanExporterGrpc
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter as OTLPMetricExporterHttp
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as OTLPSpanExporterHttp
from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPX2ClientInstrumentor
from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, MetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SpanExporter
from pydantic import AliasChoices, BaseModel, Field, UrlConstraints, field_validator
from pydantic_core import Url

logger = logging.getLogger(__name__)

OtlpUrl = Annotated[Url, UrlConstraints(allowed_schemes=["http", "https", "grpc", "console"])]

DEFAULT_OTLP_SERVICE_NAME = "dnstapir"
DEFAULT_OTLP_GRPC_PORT = 4317

_configured = False


class OtlpSettings(BaseModel):
    service_name: str | None = None
    spans_endpoint: OtlpUrl | None = Field(
        default=None,
        description="Endpoint for OTLP spans, e.g., 'grpc://localhost:4317' or 'http://localhost:4318/v1/traces'",
    )
    metrics_endpoint: OtlpUrl | None = Field(
        default=None,
        description="Endpoint for OTLP metrics, e.g., 'grpc://localhost:4317' or 'http://localhost:4318/v1/metrics'",
    )
    insecure_grpc: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("insecure_grpc", "insecure"),
        description="Whether to use an insecure connection for OTLP gRPC endpoints (default is a TLS connection)",
    )

    @field_validator("spans_endpoint", "metrics_endpoint", mode="before")
    @classmethod
    def grpc_host_port(cls, value: Any) -> Any:
        # If the value is a bare host:port string, prepend "grpc://" to make it a valid URL
        if isinstance(value, str) and (match := re.match(r"^([\w\.\-]+:\d+)$", value)):
            return f"grpc://{match.group(1)}"
        return value

    @field_validator("spans_endpoint", "metrics_endpoint", mode="after")
    @classmethod
    def check_grpc_path(cls, value: OtlpUrl | None) -> OtlpUrl | None:
        if isinstance(value, Url) and value.scheme == "grpc":
            if value.path and value.path != "/":
                raise ValueError("gRPC path not supported")
            if value.query:
                raise ValueError("gRPC query parameter not supported")
        return value

    def get_spans_exporter(self) -> SpanExporter | None:
        """Get the appropriate OTLP span exporter based on the spans endpoint scheme."""
        if self.spans_endpoint:
            match self.spans_endpoint.scheme:
                case "grpc":
                    return OTLPSpanExporterGrpc(
                        endpoint=f"{self.spans_endpoint.host}:{self.spans_endpoint.port or DEFAULT_OTLP_GRPC_PORT}",
                        insecure=self.insecure_grpc,
                    )
                case "http" | "https":
                    return OTLPSpanExporterHttp(endpoint=str(self.spans_endpoint))
                case "console":
                    return ConsoleSpanExporter()
        return None

    def get_metrics_exporter(self) -> MetricExporter | None:
        """Get the appropriate OTLP metric exporter based on the metrics endpoint scheme."""
        if self.metrics_endpoint:
            match self.metrics_endpoint.scheme:
                case "grpc":
                    return OTLPMetricExporterGrpc(
                        endpoint=f"{self.metrics_endpoint.host}:{self.metrics_endpoint.port or DEFAULT_OTLP_GRPC_PORT}",
                        insecure=self.insecure_grpc,
                    )
                case "http" | "https":
                    return OTLPMetricExporterHttp(endpoint=str(self.metrics_endpoint))
                case "console":
                    return ConsoleMetricExporter()
        return None


def configure_opentelemetry(
    settings: OtlpSettings,
    service_name: str | None = None,
    fastapi_app: FastAPI | None = None,
) -> None:
    """Configure OpenTelemetry for tracing and metrics. Should only be called only once per process."""

    global _configured

    # Providers can only be set once per process, so only configure once
    if _configured:
        logger.debug("OpenTelemetry already configured, ignoring settings")
        return

    service_name = settings.service_name or service_name or DEFAULT_OTLP_SERVICE_NAME
    resource = Resource(attributes={SERVICE_NAME: service_name})

    # Configure tracing provider
    if spans_exporter := settings.get_spans_exporter():
        trace_provider = TracerProvider(resource=resource)
        processor = BatchSpanProcessor(spans_exporter)
        trace_provider.add_span_processor(processor)
        trace.set_tracer_provider(trace_provider)
        logger.debug("OTLP spans via %s", settings.spans_endpoint or "console")
    else:
        logger.debug("No OTLP spans exporter configured, tracing disabled")

    # Configure metrics provider
    if metrics_exporter := settings.get_metrics_exporter():
        reader = PeriodicExportingMetricReader(metrics_exporter)
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(meter_provider)
        logger.debug("OTLP metrics via %s", settings.metrics_endpoint or "console")
    else:
        logger.debug("No OTLP metrics exporter configured, metrics disabled")

    # Configure instrumentation for various libraries
    if spans_exporter or metrics_exporter:
        PymongoInstrumentor().instrument()
        BotocoreInstrumentor().instrument()
        RedisInstrumentor().instrument()
        HTTPX2ClientInstrumentor().instrument()

        if fastapi_app:
            FastAPIInstrumentor.instrument_app(
                app=fastapi_app,
                http_capture_headers_server_request=[
                    "x-request-id",
                    "traceparent",
                    "tracestate",
                ],
            )
        _configured = True
        logger.info("OpenTelemetry configured")
    else:
        logger.warning("OpenTelemetry not configured, no exporters available")
