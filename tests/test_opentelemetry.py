from fastapi import FastAPI

from dnstapir.opentelemetry import OtlpSettings, configure_opentelemetry


def test_telemetry():
    app = FastAPI()
    settings = OtlpSettings()
    configure_opentelemetry(service_name="test", settings=settings, fastapi_app=app)
