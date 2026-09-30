"""WAVE SDK test configuration."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest

LIVE_RESPONSES = json.loads(
    (Path(__file__).parent / "fixtures" / "live_responses.json").read_text()
)


@pytest.fixture
def api_key():
    return "test-api-key"


@pytest.fixture
def wave_client():
    from wave_sdk import Wave
    return Wave(api_key="test-api-key", organization_id="org_test")


def live(label: str) -> dict[str, Any]:
    """A recorded (scrubbed) live response: ``{"status", "path", "body"}``."""
    return LIVE_RESPONSES[label]


def live_response(label: str, **headers: str) -> httpx.Response:
    entry = live(label)
    return httpx.Response(entry["status"], json=entry["body"], headers=headers)


class Recorder:
    """An httpx transport handler that records every request and answers from a handler."""

    def __init__(self, handler: Callable[[httpx.Request], httpx.Response] | None = None):
        self.requests: list[httpx.Request] = []
        self._handler = handler or (lambda _r: httpx.Response(200, json={}))

    def set(self, handler: Callable[[httpx.Request], httpx.Response]) -> None:
        self._handler = handler

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._handler(request)

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]


def attach(client: Any, recorder: Recorder) -> None:
    """Point a WaveClient's HTTP pool at ``recorder`` (headers and base URL unchanged)."""
    client._client = httpx.Client(
        base_url=client.base_url,
        transport=httpx.MockTransport(recorder),
        headers=client._build_headers(),
    )


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture
def wave(recorder: Recorder, monkeypatch: pytest.MonkeyPatch):
    """A Wave facade whose every request goes to ``recorder``. Sleeping is an error, so a test
    notices any retry it did not ask for."""
    from wave_sdk import Wave

    w = Wave(api_key="test-api-key", organization_id="org_test")
    attach(w.client, recorder)

    def no_sleep(seconds: float) -> None:
        raise AssertionError(f"unexpected retry sleep ({seconds}s)")

    monkeypatch.setattr("wave_sdk.client.time.sleep", no_sleep)
    return w
