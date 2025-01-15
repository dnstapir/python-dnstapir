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

        with structlog.contextvars.bound_contextvars(request_id=request_id):
            logger.bind(
                method=request.method,
                path=request.url.path,
            ).info(
                f"Processing {request.method} request to {request.url.path}",
            )

            request.state.start_time = time.perf_counter()
            request.state.request_id = request_id
            response = await call_next(request)
            elapsed = time.perf_counter() - request.state.start_time

            logger.bind(
                path=request.url.path,
                method=request.method,
                status_code=response.status_code,
                elapsed=elapsed,
            ).info(
                f"Processed {request.method} request to {request.url.path} in {elapsed:.3f} seconds",
            )

            response.headers["X-Request-ID"] = request_id

            return response
