"""WAVE SDK - error types and the parser that maps every WAVE error body onto them.

``wave_sdk.client`` re-exports everything here, so ``from wave_sdk.client import WaveError``
keeps working.
"""
from __future__ import annotations

import math
from typing import Any

import httpx

# The gateway attaches a machine-readable `next_action` to its errors. Only these two verbs mean
# "the same request can succeed later"; every other verb (`none`, `pay`, `upgrade_plan`,
# `acquire_scope`, `authenticate`) names a condition a retry cannot clear.
_RETRY_ACTIONS = frozenset({"retry_backoff", "retry_after"})

# Codes the gateway uses when no WAVE capability answers a (method, path) pair.
_ROUTE_NOT_SERVED_CODES = frozenset({"ROUTE_NOT_MAPPED", "ROUTE_NOT_FOUND"})

# Keys of the normalized error object that map onto WaveError attributes rather than `details`.
_ERROR_OBJECT_KEYS = frozenset(
    {"code", "message", "details", "request_id", "next_action", "suggestions", "doc_url"}
)

# Top-level keys of a flat error body that are not caller-facing context.
_FLAT_BODY_SKIP = frozenset(
    {"code", "message", "next_action", "suggestions", "doc_url", "request_id",
     "accepts", "x402Version", "error_detail"}
)


class WaveError(Exception):
    """WAVE API error.

    ``code`` and ``message`` come from the response body whenever the server sent them;
    ``details`` carries any structured context (for example ``available_scopes`` on a 403).
    ``next_action`` is the gateway's machine-readable directive (``{"type": "retry_backoff"}``,
    ``{"type": "acquire_scope", "scope": ...}``, ...), and ``retryable`` follows it when present.
    """

    def __init__(
        self,
        message: str,
        code: str,
        status_code: int,
        request_id: str | None = None,
        details: dict[str, Any] | None = None,
        *,
        next_action: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        doc_url: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.request_id = request_id
        self.details = details
        self.next_action = next_action
        self.suggestions = suggestions
        self.doc_url = doc_url
        self.retryable = self._is_retryable(status_code, code)

    def _is_retryable(self, status_code: int, code: str) -> bool:
        action = self.next_action.get("type") if isinstance(self.next_action, dict) else None
        if isinstance(action, str):
            # The server said whether a retry can help; believe it over the status code, so a
            # permanent 503 (for example an unbound store) is not retried three times.
            return action in _RETRY_ACTIONS
        if status_code == 429:
            return True
        if 500 <= status_code < 600:
            return True
        return code in ("TIMEOUT", "NETWORK_ERROR", "SERVICE_UNAVAILABLE")

    @property
    def retry_after_hint(self) -> float | None:
        """Seconds to wait from a ``{"type": "retry_after", "seconds": N}`` directive, if any."""
        return _retry_after_directive(self.next_action)

    def __str__(self) -> str:
        return f"WaveError({self.code}): {self.message}"


def _wait_seconds(value: Any) -> float | None:
    """A usable wait: a finite, non-negative number (bools, NaN and infinities are rejected)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and value >= 0 else None


def _retry_after_directive(next_action: Any) -> float | None:
    if not isinstance(next_action, dict) or next_action.get("type") != "retry_after":
        return None
    return _wait_seconds(next_action.get("seconds"))


def retry_after_seconds(response: httpx.Response, next_action: Any = None) -> float:
    """How long the server asked the caller to wait before retrying.

    A numeric ``Retry-After`` header wins, then the body's ``retry_after`` directive, then 1 s. A
    header that is not a finite, non-negative number of seconds (an HTTP date, ``nan``, ``-1``)
    is ignored. The value is not capped here; the client decides whether a wait is too long to
    retry on its own.
    """
    header = response.headers.get("retry-after")
    if header:
        try:
            parsed = _wait_seconds(float(header))
        except ValueError:
            parsed = None
        if parsed is not None:
            return parsed
    directive = _retry_after_directive(next_action)
    return directive if directive is not None else 1.0


class RateLimitError(WaveError):
    """HTTP 429. ``retry_after`` is the wait the server asked for, in seconds."""

    def __init__(
        self,
        message: str,
        retry_after: float,
        request_id: str | None = None,
        **kwargs: Any,
    ):
        super().__init__(message, "RATE_LIMITED", 429, request_id, **kwargs)
        self.retry_after = retry_after


class PaymentRequiredError(WaveError):
    """HTTP 402: the request was not served because it needs payment.

    Two bodies produce this error:

    * an x402 payment challenge (no key, or an unrecognized key, on a paid route): ``accepts``
      holds the payment options, ``x402_version`` the protocol version, and ``next_action`` the
      server's ``pay`` directive;
    * a plan spend-cap refusal (code ``SPEND_CAP_TIER_BLOCKED``): ``details`` carries the
      server's ``dimension``, ``projected_cost_usd``, ``remaining_allowance_usd`` and ``reason``.
    """

    def __init__(
        self,
        message: str,
        code: str,
        request_id: str | None = None,
        details: dict[str, Any] | None = None,
        *,
        accepts: list[dict[str, Any]] | None = None,
        x402_version: int | None = None,
        **kwargs: Any,
    ):
        super().__init__(message, code, 402, request_id, details, **kwargs)
        self.accepts: list[dict[str, Any]] = accepts or []
        self.x402_version = x402_version


class RouteNotServedError(WaveError):
    """No WAVE capability serves this method and path.

    Raised for a 404 whose code says the route itself is missing (``ROUTE_NOT_MAPPED`` when the
    gateway has no rule for the path, ``ROUTE_NOT_FOUND`` when nothing is behind a mapped
    prefix, or a product's own ``*_ROUTE_NOT_FOUND``), and for a 405 (the path exists, but not
    for this method). It is never raised for a missing resource such as an unknown clip id.
    ``doc_url`` points at the free capability index when the server names one.
    """


def _as_str_list(value: Any) -> list[str] | None:
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return list(value)
    return None


def _as_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _is_route_not_served(status_code: int, code: str) -> bool:
    if status_code == 405:
        return True
    return status_code == 404 and (
        code in _ROUTE_NOT_SERVED_CODES or code.upper().endswith("_ROUTE_NOT_FOUND")
    )


def _from_envelope(err: dict[str, Any], fields: dict[str, Any]) -> None:
    """The normalized envelope: ``{"error": {"code", "message", ...}}``."""
    fields["code"] = str(err.get("code") or fields["code"])
    fields["message"] = str(err.get("message") or fields["message"])
    details = _as_dict(err.get("details"))
    # Extra members of the error object (required_scope, available_scopes, ...) are context
    # the caller can act on, so they are kept rather than dropped.
    extra = {k: v for k, v in err.items() if k not in _ERROR_OBJECT_KEYS}
    fields["details"] = {**extra, **(details or {})} if extra else details
    fields["next_action"] = _as_dict(err.get("next_action"))
    fields["suggestions"] = _as_str_list(err.get("suggestions"))
    fields["doc_url"] = err.get("doc_url") if isinstance(err.get("doc_url"), str) else None
    if isinstance(err.get("request_id"), str):
        fields["request_id"] = err["request_id"]


def _from_flat_body(body: dict[str, Any], fields: dict[str, Any]) -> None:
    """Flat bodies: ``error`` is a short reason string (or absent). The normalized object, when
    there is one, sits under ``error_detail`` (the x402 challenge) or at the top level."""
    raw_error = body.get("error")
    detail = _as_dict(body.get("error_detail")) or {}
    reason = raw_error if isinstance(raw_error, str) else None
    fields["code"] = str(detail.get("code") or body.get("code") or fields["code"])
    fields["message"] = str(detail.get("message") or body.get("message") or reason or fields["message"])
    fields["next_action"] = _as_dict(body.get("next_action")) or _as_dict(detail.get("next_action"))
    fields["suggestions"] = _as_str_list(detail.get("suggestions") or body.get("suggestions"))
    url = detail.get("doc_url") or body.get("doc_url")
    fields["doc_url"] = url if isinstance(url, str) else None
    if isinstance(body.get("accepts"), list):
        fields["accepts"] = [a for a in body["accepts"] if isinstance(a, dict)]
    if isinstance(body.get("x402Version"), int):
        fields["x402_version"] = body["x402Version"]
    extra = {k: v for k, v in body.items() if k not in _FLAT_BODY_SKIP}
    detail_extra = {k: v for k, v in detail.items() if k not in _ERROR_OBJECT_KEYS}
    merged = {**detail_extra, **extra, **(_as_dict(detail.get("details")) or {})}
    fields["details"] = merged or None


def error_from_response(response: httpx.Response) -> WaveError:
    """Build the most specific WaveError for a non-2xx response.

    Understands every error body the WAVE API returns:

    * the normalized envelope ``{"error": {"code", "message", "details", "next_action", ...}}``;
    * a flat body ``{"error": "<short reason>", "code": ..., "message": ..., <context>}``
      (for example a spend-cap refusal), and the bare ``{"error": "<reason>"}`` form;
    * the x402 challenge ``{"x402Version", "error": "payment required", "accepts": [...],
      "error_detail": {...}, "next_action": {...}}``.

    Anything else (a non-JSON body) falls back to code ``HTTP_<status>``.
    """
    status = response.status_code
    fallback_message = f"HTTP {status}: {response.reason_phrase}"
    fields: dict[str, Any] = {
        "code": f"HTTP_{status}",
        "message": fallback_message,
        "details": None, "next_action": None, "suggestions": None, "doc_url": None,
        "request_id": None, "accepts": None, "x402_version": None,
    }
    try:
        body = response.json()
    except ValueError:  # not JSON (JSONDecodeError), or not text (UnicodeDecodeError)
        body = None

    if isinstance(body, dict):
        if isinstance(body.get("request_id"), str):
            fields["request_id"] = body["request_id"]
        if isinstance(body.get("error"), dict):
            _from_envelope(body["error"], fields)
        else:
            _from_flat_body(body, fields)

    request_id = response.headers.get("x-request-id") or fields["request_id"]
    message, code, details = fields["message"], fields["code"], fields["details"]
    common: dict[str, Any] = {
        "next_action": fields["next_action"],
        "suggestions": fields["suggestions"],
        "doc_url": fields["doc_url"],
    }
    if status == 429:
        # One class for a 429 wherever it comes from (a REST call or a WebSocket upgrade).
        return RateLimitError(
            message if message != fallback_message else "Rate limit exceeded",
            retry_after_seconds(response, fields["next_action"]),
            request_id,
            details=details,
            **common,
        )
    if status == 402:
        return PaymentRequiredError(
            message, code, request_id, details,
            accepts=fields["accepts"], x402_version=fields["x402_version"], **common,
        )
    if _is_route_not_served(status, code):
        return RouteNotServedError(message, code, status, request_id, details, **common)
    return WaveError(message, code, status, request_id, details, **common)
