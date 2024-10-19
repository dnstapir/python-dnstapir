from fastapi import FastAPI

from tapir.telemetry import configure_opentelemetry


def test_telemetry():
    app = FastAPI()
    configure_opentelemetry(app, service_name="test")
