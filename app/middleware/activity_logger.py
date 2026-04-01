"""
Middleware that logs every request for audit purposes.
"""

import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("examinal.access")


class ActivityLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed = time.perf_counter() - start

        logger.info(
            "%s %s %s %.3fs %s",
            request.client.host if request.client else "-",
            request.method,
            request.url.path,
            elapsed,
            response.status_code,
        )
        response.headers["X-Process-Time"] = f"{elapsed:.4f}"
        return response