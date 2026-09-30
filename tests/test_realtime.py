"""Realtime: the REST calls and the WebSocket upgrade target the API host's published operations,
carry the org header, and never put the API key in a URL.

Published operations (api.wave.online, prefix /v1):
  realtimePublish   POST /realtime/channels/{channel}/publish
  realtimePresence  GET  /realtime/channels/{channel}/presence
  realtimeHistory   GET  /realtime/channels/{channel}/history
  realtimeConnect   GET  /realtime/connect   (WebSocket upgrade)
"""
from __future__ import annotations

import sys
import types
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from tests.conftest import live_response
from wave_sdk import PaymentRequiredError, RouteNotServedError, WaveError
from wave_sdk.client import WaveClient
from wave_sdk.realtime import RealtimeAPI, _channel_path

KEY = "test-realtime-key"


class _FakeSocket:
    def __init__(self, url: str, header: list[str] | None = None) -> None:
        self.url = url
        self.header = header or []


@pytest.fixture
def captured_ws(monkeypatch):
    """Stub the optional ``websocket-client`` dependency and capture the upgrade it would do."""
    calls: list[_FakeSocket] = []

    def create_connection(url: str, header: list[str] | None = None, **_kw: object) -> _FakeSocket:
        sock = _FakeSocket(url, header)
        calls.append(sock)
        return sock

    module = types.ModuleType("websocket")
    module.create_connection = create_connection  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "websocket", module)
    return calls


# --- REST ---------------------------------------------------------------------------------------


def test_presence_uses_the_published_path_on_the_api_host(wave, recorder):
    recorder.set(lambda _r: live_response("realtime_presence"))
    body = wave.realtime.presence("stream:fixture")
    req = recorder.last
    assert req.method == "GET"
    assert req.url.host == "api.wave.online"
    assert req.url.raw_path == b"/v1/realtime/channels/stream:fixture/presence"
    assert body == {"channel": "stream:fixture", "members": []}


def test_history_and_publish_paths(wave, recorder):
    recorder.set(lambda _r: httpx.Response(200, json={"ok": True}))
    wave.realtime.history("probe", limit=5)
    assert recorder.last.url.raw_path == b"/v1/realtime/channels/probe/history?limit=5"
    wave.realtime.publish("probe", "sdk.test", {"n": 1})
    req = recorder.last
    assert req.method == "POST"
    assert req.url.raw_path == b"/v1/realtime/channels/probe/publish"
    assert req.content == b'{"event":"sdk.test","data":{"n":1}}'


def test_rest_calls_carry_auth_and_org_headers(wave, recorder):
    wave.realtime.presence("probe")
    assert recorder.last.headers["authorization"] == "Bearer test-api-key"
    assert recorder.last.headers["x-organization-id"] == "org_test"


def test_channel_is_one_encoded_path_segment(wave, recorder):
    wave.realtime.presence("a/../b?x=1#f")
    assert recorder.last.url.raw_path == b"/v1/realtime/channels/a%2F..%2Fb%3Fx%3D1%23f/presence"


def test_channel_colon_stays_literal():
    # The API answers 404 for stream%3Aabc and 200 for stream:abc.
    assert _channel_path("stream:abc") == "stream:abc"


def test_rest_errors_raise_instead_of_returning_the_error_body(wave, recorder):
    recorder.set(lambda _r: live_response("err_scope_insufficient_403"))
    with pytest.raises(WaveError) as exc:
        wave.realtime.publish("probe", "evt")
    assert exc.value.code == "SCOPE_INSUFFICIENT"
    recorder.set(lambda _r: live_response("err_route_not_found_404"))
    with pytest.raises(RouteNotServedError):
        wave.realtime.history("probe")


# --- WebSocket ----------------------------------------------------------------------------------


def _api(**client_kwargs) -> RealtimeAPI:
    return RealtimeAPI(WaveClient(api_key=KEY, **client_kwargs))


def test_connect_targets_the_published_operation(captured_ws):
    _api().connect("stream:abc")
    url = urlsplit(captured_ws[0].url)
    assert (url.scheme, url.netloc, url.path) == ("wss", "api.wave.online", "/v1/realtime/connect")
    assert parse_qs(url.query) == {"channel": ["stream:abc"]}


def test_connect_follows_a_custom_base_url(captured_ws):
    _api(base_url="http://localhost:8787").connect("c")
    assert captured_ws[0].url.startswith("ws://localhost:8787/v1/realtime/connect?")


def test_api_key_travels_only_in_the_upgrade_header(captured_ws):
    _api().connect("stream:abc")
    assert KEY not in captured_ws[0].url
    assert "access_token" not in captured_ws[0].url
    assert f"Authorization: Bearer {KEY}" in captured_ws[0].header


def test_upgrade_carries_the_organization(captured_ws):
    _api(organization_id="org_123").connect("stream:abc")
    assert "X-Organization-Id: org_123" in captured_ws[0].header
    _api().connect("stream:abc")
    assert not any(h.startswith("X-Organization-Id") for h in captured_ws[1].header)


def test_channel_and_as_cannot_inject_query_parameters(captured_ws):
    _api().connect("stream:abc&as=victim", as_="user&admin=1")
    query = parse_qs(urlsplit(captured_ws[0].url).query)
    assert query == {"channel": ["stream:abc&as=victim"], "as": ["user&admin=1"]}


def test_rejected_upgrade_raises_the_same_error_as_rest(monkeypatch):
    challenge = live_response("err_x402_challenge_402")

    # Stands in for websocket-client's WebSocketBadStatusException.
    class BadStatusError(Exception):
        status_code = 402
        resp_body = challenge.content
        resp_headers = {"content-type": "application/json"}

    def create_connection(url, header=None, **_kw):
        raise BadStatusError("Handshake status 402")

    module = types.ModuleType("websocket")
    module.create_connection = create_connection  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "websocket", module)
    with pytest.raises(PaymentRequiredError) as exc:
        _api().connect("stream:abc")
    assert exc.value.accepts and exc.value.accepts[0]["resource"] == "/v1/clips"


def test_rate_limited_upgrade_raises_rate_limit_error(monkeypatch):
    """A 429 on the upgrade is the same RateLimitError (with retry_after) a REST call raises."""
    from wave_sdk import RateLimitError

    class BadStatusError(Exception):
        status_code = 429
        resp_body = b'{"error": {"code": "RATE_LIMITED", "message": "too many sockets"}}'
        resp_headers = {"content-type": "application/json", "retry-after": "5"}

    def create_connection(url, header=None, **_kw):
        raise BadStatusError("Handshake status 429")

    module = types.ModuleType("websocket")
    module.create_connection = create_connection  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "websocket", module)
    with pytest.raises(RateLimitError) as exc:
        _api().connect("stream:abc")
    assert exc.value.retry_after == 5.0
    assert exc.value.message == "too many sockets"


def test_network_failure_on_upgrade_is_not_swallowed(monkeypatch):
    def create_connection(url, header=None, **_kw):
        raise OSError("connection refused")

    module = types.ModuleType("websocket")
    module.create_connection = create_connection  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "websocket", module)
    with pytest.raises(OSError):
        _api().connect("stream:abc")
