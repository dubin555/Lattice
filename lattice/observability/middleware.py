"""
FastAPI middleware for OpenTelemetry metrics collection.

This module provides middleware for collecting API request metrics
using OpenTelemetry instrumentation.
"""

import re
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from lattice.observability.metrics import record_api_request


# Pre-compiled regex patterns for path normalization
_UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
_NUMERIC_ID_PATTERN = re.compile(r"/\d+(/|$)")


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect API request metrics using OpenTelemetry."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip metrics endpoint to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        # Normalize path to avoid high cardinality
        path = self._normalize_path(request.url.path)

        start_time = time.time()
        status_code = 500  # Default for exceptions

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            raise
        finally:
            duration = time.time() - start_time
            record_api_request(method, path, status_code, duration)

    def _normalize_path(self, path: str) -> str:
        """
        Normalize path to reduce cardinality.

        Replaces dynamic segments (UUIDs, IDs) with placeholders.
        """
        # Replace UUIDs with placeholder
        path = _UUID_PATTERN.sub("{id}", path)

        # Replace numeric IDs with placeholder
        path = _NUMERIC_ID_PATTERN.sub("/{id}\\1", path)

        return path
