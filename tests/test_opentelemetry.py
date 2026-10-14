import pytest
from fastapi import FastAPI
from opentelemetry import metrics, trace

from dnstapir.opentelemetry import OtlpSettings, configure_opentelemetry


@pytest.fixture(scope="module", autouse=True)
def shutdown_providers():
    """Flush console exporters while pytest's output capture is still open"""
    yield
    trace.get_tracer_provider().shutdown()
    metrics.get_meter_provider().shutdown()


def test_telemetry():
    app = FastAPI()
    settings = OtlpSettings()
    configure_opentelemetry(service_name="test", settings=settings, fastapi_app=app)


def test_telemetry_twice():
    settings = OtlpSettings()
    configure_opentelemetry(service_name="test", settings=settings)
    tracer_provider = trace.get_tracer_provider()
    meter_provider = metrics.get_meter_provider()

    app = FastAPI()
    configure_opentelemetry(service_name="test", settings=settings, fastapi_app=app)
    assert trace.get_tracer_provider() is tracer_provider
    assert metrics.get_meter_provider() is meter_provider
    assert app._is_instrumented_by_opentelemetry
