from fastapi import FastAPI
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from dnstapir.starlette import LoggingMiddleware


def test_starlette():
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)
    client = TestClient(app, client=("127.0.0.1", "1984"), headers={"X-Forwarded-For": "10.0.0.1"})
    client.get("/")


def test_starlette_proxy():
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["127.0.0.1"])
    client = TestClient(app, client=("127.0.0.1", 1984), headers={"X-Forwarded-For": "10.0.0.1"})
    client.get("/proxy")
