"""
WAVE SDK - Base API Client

Core HTTP client with authentication, rate limiting, and retry logic.
"""

from __future__ import annotations

import time
import logging
from typing import Any, TypeVar, Generic
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel

logger = logging.getLogger("wave")

T = TypeVar("T")


class WaveError(Exception):
    """WAVE API error."""

    def __init__(
        self,
        message: str,
        code: str,
        status_code: int,
        request_id: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.request_id = request_id
        self.details = details
        self.retryable = self._is_retryable(status_code, code)

    def _is_retryable(self, status_code: int, code: str) -> bool:
        if status_code == 429:
            return True
        if 500 <= status_code < 600:
            return True
        if code in ("TIMEOUT", "NETWORK_ERROR", "SERVICE_UNAVAILABLE"):
            return True
        return False

    def __str__(self) -> str:
        return f"WaveError({self.code}): {self.message}"


class RateLimitError(WaveError):
    """Rate limit exceeded error."""

    def __init__(
        self,
        message: str,
        retry_after: float,
        request_id: str | None = None,
    ):
        super().__init__(message, "RATE_LIMITED", 429, request_id)
        self.retry_after = retry_after


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
        >>> response = client.get("/v1/clips")
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
            "User-Agent": "wave-sdk-python/1.0.0",
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
        **kwargs: Any,
    ) -> Any:
        """Make an API request with retry logic."""
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
                    retry_after = self._parse_retry_after(response)
                    if attempt < max_retries:
                        logger.warning(f"Rate limited. Retrying in {retry_after}s")
                        time.sleep(retry_after)
                        continue
                    raise RateLimitError(
                        "Rate limit exceeded",
                        retry_after,
                        response.headers.get("x-request-id"),
                    )

                # Handle errors
                if not response.is_success:
                    error = self._parse_error(response)
                    if error.retryable and attempt < max_retries:
                        delay = self._calculate_backoff(attempt)
                        logger.warning(f"Request failed. Retrying in {delay}s")
                        time.sleep(delay)
                        continue
                    raise error

                # Parse response
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
        """Parse error response."""
        request_id = response.headers.get("x-request-id")
        try:
            body = response.json()
            return WaveError(
                body.get("error", {}).get("message", f"HTTP {response.status_code}"),
                body.get("error", {}).get("code", f"HTTP_{response.status_code}"),
                response.status_code,
                request_id or body.get("request_id"),
                body.get("error", {}).get("details"),
            )
        except Exception:
            return WaveError(
                f"HTTP {response.status_code}: {response.reason_phrase}",
                f"HTTP_{response.status_code}",
                response.status_code,
                request_id,
            )

    def _parse_retry_after(self, response: httpx.Response) -> float:
        """Parse Retry-After header."""
        retry_after = response.headers.get("retry-after")
        if not retry_after:
            return 1.0
        try:
            return float(retry_after)
        except ValueError:
            return 1.0

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        base_delay = 1.0
        max_delay = 30.0
        delay = min(base_delay * (2**attempt), max_delay)
        # Add jitter
        import random

        return delay + random.random() * delay * 0.25

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "WaveClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
