"""Starlette middleware and other utilities"""

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        logger = structlog.get_logger()
        request_id = str(uuid.uuid4())

        remote = (
            {
                "client_host": str(request.client.host),
                "client_port": str(request.client.port),
            }
            if request.client
            else {}
        )

        with structlog.contextvars.bound_contextvars(request_id=request_id):
            logger.bind(
                **remote,
                method=request.method,
                path=request.url.path,
            ).info(
                f"Processing {request.method} request from {request.client.host} to {request.url.path}",
            )

            request.state.start_time = time.perf_counter()
            request.state.request_id = request_id
            response = await call_next(request)
            elapsed = time.perf_counter() - request.state.start_time

            logger.bind(
                **remote,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                elapsed=elapsed,
            ).info(
                f"Processed {request.method} request from {request.client.host} to {request.url.path} in {elapsed:.3f} seconds",
            )

            response.headers["X-Request-ID"] = request_id

            return response
