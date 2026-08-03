"""Realtime auth-transport tests.

Covers two defects that were live on main:

1. ``RealtimeAPI`` built its own header dict and omitted ``X-Organization-Id``, so every realtime
   operation ran unscoped while the rest of the SDK carried the tenant.
2. The API key travelled in the WebSocket URL query string, where every hop that logs a request
   line records it.
"""
from __future__ import annotations

import sys
import types
from wave.client import WaveClient
from wave.realtime import RealtimeAPI

import pytest


class _FakeSocket:
    def __init__(self, url: str, header: list[str] | None = None, **_: object) -> None:
        self.url = url
        self.header = header or []


@pytest.fixture
def captured_ws(monkeypatch):
    """Stub the optional ``websocket-client`` dep and capture the upgrade it would perform."""
    calls: list[_FakeSocket] = []

    def create_connection(url: str, header: list[str] | None = None, **kwargs: object) -> _FakeSocket:
        sock = _FakeSocket(url, header, **kwargs)
        calls.append(sock)
        return sock

    module = types.ModuleType("websocket")
    module.create_connection = create_connection  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "websocket", module)
    return calls


def _api(**client_kwargs) -> RealtimeAPI:
    client = WaveClient(api_key="sk-test-key", **client_kwargs)
    return RealtimeAPI(client)


# --- Finding 1: multi-tenant isolation -------------------------------------------------------


def test_rest_headers_carry_the_organization():
    headers = _api(organization_id="org_123")._headers()
    assert headers["X-Organization-Id"] == "org_123"
    assert headers["Authorization"] == "Bearer sk-test-key"


def test_rest_headers_omit_the_organization_when_unset():
    assert "X-Organization-Id" not in _api()._headers()


def test_ws_upgrade_carries_the_organization(captured_ws):
    _api(organization_id="org_123").connect("stream:abc")
    assert "X-Organization-Id: org_123" in captured_ws[0].header


def test_rest_path_encodes_the_channel():
    from wave.realtime import _channel_path

    assert _channel_path("stream:abc") == "stream:abc"
    assert _channel_path("a/../b") == "a%2F..%2Fb"


# --- Finding 2: credential in the URL --------------------------------------------------------


def test_api_key_is_not_in_the_connect_url(captured_ws):
    _api(organization_id="org_123").connect("stream:abc")
    assert "sk-test-key" not in captured_ws[0].url
    assert "access_token" not in captured_ws[0].url


def test_api_key_travels_in_the_upgrade_header(captured_ws):
    _api().connect("stream:abc")
    assert "Authorization: Bearer sk-test-key" in captured_ws[0].header


def test_legacy_query_token_is_opt_in(captured_ws):
    client = WaveClient(api_key="sk-test-key")
    RealtimeAPI(client, token_in_query=True).connect("stream:abc")
    assert "access_token=sk-test-key" in captured_ws[0].url
    # The header is still sent — opting into the legacy param does not disable the correct path.
    assert "Authorization: Bearer sk-test-key" in captured_ws[0].header


# --- Finding 3: query-parameter injection ----------------------------------------------------


def test_channel_cannot_inject_a_query_parameter(captured_ws):
    _api().connect("stream:abc&as=victim")
    url = captured_ws[0].url
    assert "&as=victim" not in url
    assert "as%3Dvictim" in url


def test_as_parameter_is_encoded(captured_ws):
    _api().connect("stream:abc", as_="user&admin=1")
    url = captured_ws[0].url
    assert "&admin=1" not in url
