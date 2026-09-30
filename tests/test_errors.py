"""Error parsing and retry behaviour, driven by response bodies recorded from the live API.

Every body in tests/fixtures/live_responses.json was returned by https://api.wave.online (ids
scrubbed). The API uses three error shapes, and before 2.3.0 the client only understood the
first, so the other two surfaced as a bare ``HTTP 402: Payment Required``:

* the normalized envelope ``{"error": {"code", "message", ...}}``;
* a flat body ``{"error": "<reason>", "code", "message", ...}`` (spend-cap refusal), or just
  ``{"error": "<reason>"}``;
* the x402 payment challenge ``{"x402Version", "error": "payment required", "accepts": [...]}``.
"""
from __future__ import annotations

import httpx
import pytest

from tests.conftest import live, live_response
from wave_sdk import PaymentRequiredError, RateLimitError, RouteNotServedError, WaveError
from wave_sdk.errors import error_from_response


def parse(label: str, **headers: str) -> WaveError:
    return error_from_response(live_response(label, **headers))


# --- the three shapes --------------------------------------------------------------------------


def test_spend_cap_refusal_keeps_the_server_code_message_and_context():
    err = parse("err_spend_cap_402")
    assert isinstance(err, PaymentRequiredError)
    assert err.status_code == 402
    assert err.code == "SPEND_CAP_TIER_BLOCKED"
    assert err.message.startswith("Add a payment method to continue")
    assert err.details is not None
    assert err.details["projected_cost_usd"] == 0
    assert err.details["dimension"] == "wave_clip_minutes"
    assert err.details["error"] == "spend_cap_exceeded"
    assert err.accepts == []
    assert err.retryable is False


def test_x402_challenge_exposes_the_payment_options():
    err = parse("err_x402_challenge_402")
    assert isinstance(err, PaymentRequiredError)
    assert err.code == "PAYMENT_REQUIRED"
    assert "x402" in err.message
    assert err.x402_version == 1
    assert err.accepts and err.accepts[0]["scheme"] == "exact"
    assert err.accepts[0]["resource"] == "/v1/clips"
    assert err.next_action is not None and err.next_action["type"] == "pay"
    assert err.retryable is False


def test_bare_reason_string_becomes_the_message():
    err = parse("err_missing_node_400")
    assert type(err) is WaveError
    assert err.code == "HTTP_400"
    assert err.message == "missing x-wave-node"


def test_method_not_allowed_is_a_route_not_served_error():
    err = parse("err_method_not_allowed_405")
    assert isinstance(err, RouteNotServedError)
    assert err.status_code == 405
    assert err.message == "method not allowed"


@pytest.mark.parametrize(
    "label, code",
    [
        ("err_route_not_mapped_404", "ROUTE_NOT_MAPPED"),
        ("err_route_not_found_404", "ROUTE_NOT_FOUND"),
        ("err_product_route_not_found_404", "search_route_not_found"),
    ],
)
def test_missing_routes_are_route_not_served_errors(label, code):
    err = parse(label)
    assert isinstance(err, RouteNotServedError)
    assert err.code == code
    assert err.retryable is False


def test_route_not_served_carries_the_capability_index_url():
    err = parse("err_route_not_mapped_404")
    assert err.doc_url and err.doc_url.endswith("/.well-known/wave-skills.json")
    assert err.suggestions and len(err.suggestions) >= 1


def test_a_missing_resource_is_not_a_route_error():
    response = httpx.Response(404, json={"error": {"code": "CLIP_NOT_FOUND", "message": "no clip"}})
    err = error_from_response(response)
    assert type(err) is WaveError
    assert err.code == "CLIP_NOT_FOUND"


def test_scope_error_keeps_required_and_available_scopes():
    err = parse("err_scope_insufficient_403")
    assert err.code == "SCOPE_INSUFFICIENT"
    assert err.details is not None
    assert "required_scope" in err.details
    assert isinstance(err.details["available_scopes"], list)


def test_request_id_prefers_the_header_then_the_body():
    assert parse("err_route_not_found_404", **{"x-request-id": "req-header"}).request_id == "req-header"
    assert parse("err_route_not_found_404").request_id == live("err_route_not_found_404")["body"]["error"]["request_id"]


def test_non_json_body_falls_back_to_the_status():
    err = error_from_response(httpx.Response(502, text="<html>bad gateway</html>"))
    assert err.code == "HTTP_502"
    assert err.message.startswith("HTTP 502")
    assert err.retryable is True


def test_str_names_the_code():
    assert str(parse("err_spend_cap_402")).startswith("WaveError(SPEND_CAP_TIER_BLOCKED)")


# --- retry decisions follow the server's next_action --------------------------------------------


def test_permanent_503_is_not_retried(wave, recorder):
    """COMPOSE_STORE_UNCONFIGURED says next_action none: one request, no backoff sleeps."""
    recorder.set(lambda _r: live_response("err_store_unconfigured_503"))
    with pytest.raises(WaveError) as exc:
        wave.compose.get_proposal("prp_aaaaaaaaaaaaaaaaaaaa")
    assert exc.value.code == "COMPOSE_STORE_UNCONFIGURED"
    assert exc.value.retryable is False
    assert len(recorder.requests) == 1


def test_retry_backoff_directive_is_retried(wave, recorder, monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("wave_sdk.client.time.sleep", sleeps.append)
    upstream = {"error": {"code": "UPSTREAM_ERROR", "message": "upstream failed", "next_action": {"type": "retry_backoff"}}}
    replies = iter([httpx.Response(500, json=upstream), httpx.Response(200, json={"org": "o", "range": {"from": "20260901", "to": "20260901", "days": 1}, "totals": {}})])
    recorder.set(lambda _r: next(replies))
    report = wave.usage.get()
    assert report.org == "o"
    assert len(recorder.requests) == 2 and len(sleeps) == 1


def test_retry_after_directive_sets_the_delay(wave, recorder, monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("wave_sdk.client.time.sleep", sleeps.append)
    busy = {"error": {"code": "BUSY", "message": "try later", "next_action": {"type": "retry_after", "seconds": 7}}}
    replies = iter([httpx.Response(503, json=busy), httpx.Response(200, json={"ok": True})])
    recorder.set(lambda _r: next(replies))
    assert wave.client.get("/v1/anything") == {"ok": True}
    assert sleeps == [7.0]


def test_rate_limit_error_keeps_the_server_message(wave, recorder, monkeypatch):
    monkeypatch.setattr("wave_sdk.client.time.sleep", lambda _s: None)
    body = {"error": {"code": "RATE_LIMITED", "message": "slow down", "next_action": {"type": "retry_after", "seconds": 2}}}
    recorder.set(lambda _r: httpx.Response(429, json=body, headers={"retry-after": "3"}))
    with pytest.raises(RateLimitError) as exc:
        wave.client.get("/v1/anything")
    assert exc.value.message == "slow down"
    assert exc.value.retry_after == 3.0
    assert len(recorder.requests) == wave.client.max_retries + 1


def test_a_429_is_a_rate_limit_error_wherever_it_is_parsed():
    """The parser, not the REST loop, picks the class, so a WebSocket upgrade gets it too."""
    err = error_from_response(httpx.Response(429, json={"error": "slow down"}, headers={"retry-after": "4"}))
    assert isinstance(err, RateLimitError)
    assert err.message == "slow down"
    assert err.retry_after == 4.0
    bare = error_from_response(httpx.Response(429))
    assert isinstance(bare, RateLimitError) and bare.message == "Rate limit exceeded" and bare.retry_after == 1.0


def test_a_permanent_429_is_not_retried(wave, recorder):
    """A 429 whose directive is not a retry (here: a plan limit) is raised on the first attempt."""
    body = {"error": {"code": "PLAN_LIMIT", "message": "monthly cap reached", "next_action": {"type": "upgrade_plan"}}}
    recorder.set(lambda _r: httpx.Response(429, json=body, headers={"retry-after": "1"}))
    with pytest.raises(RateLimitError) as exc:
        wave.client.get("/v1/anything")
    assert exc.value.retryable is False
    assert len(recorder.requests) == 1


def test_a_long_retry_after_is_raised_not_slept_through(wave, recorder):
    """Retry-After: 86400 used to become time.sleep(86400). It is raised at once with the full wait."""
    recorder.set(lambda _r: httpx.Response(429, json={"error": {"code": "RATE_LIMITED", "message": "m"}}, headers={"retry-after": "86400"}))
    with pytest.raises(RateLimitError) as exc:
        wave.client.get("/v1/anything")
    assert exc.value.retry_after == 86400.0
    assert len(recorder.requests) == 1


def test_a_long_retry_after_directive_is_raised_not_slept_through(wave, recorder):
    busy = {"error": {"code": "BUSY", "message": "m", "next_action": {"type": "retry_after", "seconds": 3600}}}
    recorder.set(lambda _r: httpx.Response(503, json=busy))
    with pytest.raises(WaveError) as exc:
        wave.client.get("/v1/anything")
    assert exc.value.retry_after_hint == 3600.0
    assert len(recorder.requests) == 1


@pytest.mark.parametrize("header", ["nan", "inf", "-1", "Wed, 21 Oct 2026 07:28:00 GMT", "soon"])
def test_an_unusable_retry_after_header_falls_back(wave, recorder, monkeypatch, header):
    """nan / inf / negative values reached time.sleep() and escaped as ValueError or OverflowError."""
    sleeps: list[float] = []
    monkeypatch.setattr("wave_sdk.client.time.sleep", sleeps.append)
    replies = iter([httpx.Response(429, headers={"retry-after": header}), httpx.Response(200, json={"ok": True})])
    recorder.set(lambda _r: next(replies))
    assert wave.client.get("/v1/anything") == {"ok": True}
    assert sleeps == [1.0]


def test_a_non_finite_directive_is_ignored():
    err = error_from_response(httpx.Response(503, content=b'{"error": {"code": "BUSY", "message": "m", "next_action": {"type": "retry_after", "seconds": Infinity}}}', headers={"content-type": "application/json"}))
    assert err.retry_after_hint is None


# --- the README's error-handling example --------------------------------------------------------


def test_readme_example_surfaces_the_spend_cap_message(wave, recorder):
    recorder.set(lambda _r: live_response("err_spend_cap_402"))
    with pytest.raises(PaymentRequiredError) as exc:
        wave.clips.get("invalid-id")
    assert exc.value.code == "SPEND_CAP_TIER_BLOCKED"
    assert "payment method" in exc.value.message
    assert len(recorder.requests) == 1


def test_error_classes_are_importable_from_the_client_module_too():
    from wave_sdk import client

    assert client.WaveError is WaveError
    assert issubclass(client.PaymentRequiredError, WaveError)
    assert issubclass(client.RouteNotServedError, WaveError)
