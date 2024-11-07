from fastapi import FastAPI

from dnstapir.opentelemetry import configure_opentelemetry


def test_telemetry():
    app = FastAPI()
    configure_opentelemetry(service_name="test", fastapi_app=app)
