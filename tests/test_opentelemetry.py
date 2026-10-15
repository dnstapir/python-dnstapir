import pytest
from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter as OTLPMetricExporterGrpc
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as OTLPSpanExporterGrpc
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter as OTLPMetricExporterHttp
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as OTLPSpanExporterHttp
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
from opentelemetry.sdk.trace.export import ConsoleSpanExporter

from dnstapir.opentelemetry import OtlpSettings, configure_opentelemetry


@pytest.fixture(scope="module", autouse=True)
def shutdown_providers():
    """Flush console exporters while pytest's output capture is still open"""

    yield
    trace.get_tracer_provider().shutdown()
    metrics.get_meter_provider().shutdown()


def test_telemetry_settings():
    """Test basic OTLP settings."""

    res = OtlpSettings()
    assert res.spans_endpoint is None
    assert res.metrics_endpoint is None
    assert isinstance(res.get_spans_exporter(), ConsoleSpanExporter)
    assert isinstance(res.get_metrics_exporter(), ConsoleMetricExporter)

    res = OtlpSettings(
        spans_endpoint="grpc://localhost:4317",
        metrics_endpoint="http://localhost:4318/v1/metrics",
    )
    assert res.spans_endpoint.scheme == "grpc"
    assert res.spans_endpoint.host == "localhost"
    assert res.spans_endpoint.port == 4317
    assert res.metrics_endpoint.scheme == "http"
    assert res.metrics_endpoint.host == "localhost"
    assert res.metrics_endpoint.port == 4318


def test_telemetry_settings_invalid():
    """Test that invalid OTLP settings raise ValueError."""

    with pytest.raises(ValueError):
        _ = OtlpSettings(
            metrics_endpoint="grpc://localhost:4317/xyzzy",
        )

    with pytest.raises(ValueError):
        _ = OtlpSettings(
            metrics_endpoint="grpc://localhost:4317?foo=bar",
        )


def test_telemetry_settings_compat():
    """Test compatibility with various OTLP settings formats."""

    res = OtlpSettings(spans_endpoint="localhost:4317")
    assert res.spans_endpoint.scheme == "grpc"
    assert res.spans_endpoint.host == "localhost"
    assert res.spans_endpoint.port == 4317

    res = OtlpSettings(spans_endpoint="127.0.0.1:4317")
    assert res.spans_endpoint.scheme == "grpc"
    assert res.spans_endpoint.host == "127.0.0.1"
    assert res.spans_endpoint.port == 4317

    res = OtlpSettings(insecure=True)
    assert res.insecure_grpc


@pytest.mark.parametrize(
    "spans_endpoint,metrics_endpoint,spans_exporter_class,metrics_exporter_class",
    [
        (
            "grpc://localhost:4317",
            "grpc://localhost:4317",
            OTLPSpanExporterGrpc,
            OTLPMetricExporterGrpc,
        ),
        (
            "http://localhost:4318/v1/traces",
            "http://localhost:4318/v1/metrics",
            OTLPSpanExporterHttp,
            OTLPMetricExporterHttp,
        ),
    ],
)
def test_exporters_otlp(
    spans_endpoint: str,
    metrics_endpoint: str,
    spans_exporter_class: type,
    metrics_exporter_class: type,
):
    """Test that the correct OTLP exporters are returned based on the settings."""

    # configure_opentelemetry() only builds exporters on its first call, so test the getters directly
    settings = OtlpSettings(spans_endpoint=spans_endpoint, metrics_endpoint=metrics_endpoint)

    spans_exporter = settings.get_spans_exporter()
    assert isinstance(spans_exporter, spans_exporter_class)
    spans_exporter.shutdown()

    metrics_exporter = settings.get_metrics_exporter()
    assert isinstance(metrics_exporter, metrics_exporter_class)
    metrics_exporter.shutdown()


def test_telemetry_console():
    """Test configuring OpenTelemetry with a FastAPI app."""

    app = FastAPI()
    settings = OtlpSettings()
    configure_opentelemetry(service_name="test", settings=settings, fastapi_app=app)


def test_telemetry_twice():
    """Test that configuring OpenTelemetry twice does not reconfigure it."""

    settings = OtlpSettings()
    configure_opentelemetry(service_name="test", settings=settings)
    tracer_provider = trace.get_tracer_provider()
    meter_provider = metrics.get_meter_provider()

    app = FastAPI()
    configure_opentelemetry(service_name="test", settings=settings, fastapi_app=app)
    assert trace.get_tracer_provider() is tracer_provider
    assert metrics.get_meter_provider() is meter_provider
    assert app._is_instrumented_by_opentelemetry
