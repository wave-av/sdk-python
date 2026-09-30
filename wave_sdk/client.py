"""
WAVE SDK - Base API Client

Core HTTP client with authentication, rate limiting, and retry logic.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Generic, TypeVar

import httpx
from pydantic import BaseModel

# Error types live in wave_sdk.errors; they are re-exported here so existing
# `from wave_sdk.client import WaveError` imports keep working.
from wave_sdk.errors import (
    PaymentRequiredError,
    RateLimitError,
    RouteNotServedError,
    WaveError,
    error_from_response,
)

__all__ = [
    "PaginatedResponse",
    "PaymentRequiredError",
    "RateLimitError",
    "RouteNotServedError",
    "WaveClient",
    "WaveError",
    "__version__",
    "error_from_response",
]

logger = logging.getLogger("wave_sdk")

# Single source of truth for the SDK version, used both in the package's
# public __version__ (re-exported from wave_sdk/__init__.py) and here in the
# default User-Agent header, so the two can never drift.
__version__ = "2.2.0"

T = TypeVar("T")

# Longest server-suggested wait the client honours before retrying on its own.
_MAX_SERVER_RETRY_AFTER = 60.0


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response."""

    data: list[T]
    total: int
    has_more: bool
    next_cursor: str | None = None


class WaveClient:
    """
    WAVE API Base Client.

    Handles authentication, rate limiting, and retry logic for all API requests.

    Example:
        >>> client = WaveClient(api_key="your-api-key")
        >>> usage = client.get("/v1/usage")
    """

    def __init__(
        self,
        api_key: str,
        organization_id: str | None = None,
        base_url: str = "https://api.wave.online",
        timeout: float = 30.0,
        max_retries: int = 3,
        debug: bool = False,
    ):
        """
        Initialize the WAVE client.

        Args:
            api_key: API key for authentication
            organization_id: Organization ID for multi-tenant isolation
            base_url: API base URL
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            debug: Enable debug logging
        """
        if not api_key:
            raise ValueError("WAVE SDK: api_key is required")

        self.api_key = api_key
        self.organization_id = organization_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.debug = debug

        if debug:
            logging.basicConfig(level=logging.DEBUG)

        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers=self._build_headers(),
        )

    def _build_headers(self) -> dict[str, str]:
        """Build default request headers."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"wave-sdk-python/{__version__}",
        }
        if self.organization_id:
            headers["X-Organization-Id"] = self.organization_id
        return headers

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Make a GET request."""
        return self._request("GET", path, params=params, **kwargs)

    def post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Make a POST request."""
        return self._request("POST", path, json=json, params=params, **kwargs)

    def put(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Make a PUT request."""
        return self._request("PUT", path, json=json, params=params, **kwargs)

    def patch(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Make a PATCH request."""
        return self._request("PATCH", path, json=json, params=params, **kwargs)

    def delete(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Make a DELETE request."""
        return self._request("DELETE", path, params=params, **kwargs)

    def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        no_retry: bool = False,
        raw: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Make an API request with retry logic.

        Returns the decoded JSON body, or ``None`` for a non-JSON success. With ``raw=True`` the
        successful ``httpx.Response`` itself is returned, for routes that answer with bytes (audio,
        caption files); errors still raise :class:`WaveError` exactly as on the JSON path.
        """
        # Filter out None params
        if params:
            params = {k: v for k, v in params.items() if v is not None}

        max_retries = 0 if no_retry else self.max_retries
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                if self.debug:
                    logger.debug(f"[WaveSDK] {method} {path}")

                response = self._client.request(
                    method,
                    path,
                    json=json,
                    params=params,
                    **kwargs,
                )

                # Handle rate limiting
                if response.status_code == 429:
                    parsed = self._parse_error(response)
                    retry_after = self._parse_retry_after(response, parsed)
                    if attempt < max_retries:
                        logger.warning(f"Rate limited. Retrying in {retry_after}s")
                        time.sleep(retry_after)
                        continue
                    raise RateLimitError(
                        parsed.message if parsed.code != "HTTP_429" else "Rate limit exceeded",
                        retry_after,
                        parsed.request_id,
                        details=parsed.details,
                        next_action=parsed.next_action,
                        suggestions=parsed.suggestions,
                        doc_url=parsed.doc_url,
                    )

                # Handle errors
                if not response.is_success:
                    error = self._parse_error(response)
                    if error.retryable and attempt < max_retries:
                        hint = error.retry_after_hint
                        delay = (
                            min(hint, _MAX_SERVER_RETRY_AFTER)
                            if hint is not None
                            else self._calculate_backoff(attempt)
                        )
                        logger.warning(f"Request failed ({error.code}). Retrying in {delay}s")
                        time.sleep(delay)
                        continue
                    raise error

                # Parse response
                if raw:
                    return response
                if response.headers.get("content-type", "").startswith("application/json"):
                    return response.json()
                return None

            except httpx.RequestError as e:
                last_error = e
                if attempt < max_retries:
                    delay = self._calculate_backoff(attempt)
                    logger.warning(f"Request error: {e}. Retrying in {delay}s")
                    time.sleep(delay)
                    continue
                raise WaveError(
                    str(e),
                    "NETWORK_ERROR",
                    0,
                ) from e

        if last_error:
            raise last_error
        raise WaveError("Request failed after retries", "UNKNOWN_ERROR", 0)

    def _parse_error(self, response: httpx.Response) -> WaveError:
        """Parse an error response into the most specific WaveError subclass."""
        return error_from_response(response)

    def _parse_retry_after(self, response: httpx.Response, error: WaveError | None = None) -> float:
        """Seconds to wait: the Retry-After header, else the body's retry_after directive, else 1s."""
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        hint = error.retry_after_hint if error is not None else None
        if hint is not None:
            return min(hint, _MAX_SERVER_RETRY_AFTER)
        return 1.0

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        base_delay = 1.0
        max_delay = 30.0
        delay = min(base_delay * (2**attempt), max_delay)
        # Add jitter
        return delay + random.random() * delay * 0.25

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> WaveClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
