"""WAVE SDK - Realtime API.

The WAVE Realtime control & event plane (realtime.wave.online): presence, pub/sub broadcast, and the
streaming-event bus the WAVE AI products push into. Subscribe once to a channel and receive live
transcription / captions / sentiment / clip / stream events with no polling.

WebSocket support uses the optional ``websocket-client`` package: ``pip install 'wave-sdk[realtime]'``.
Auth, scope, entitlement, and metering are enforced server-side (the gateway, via realtime's /v1/verify
federation) — the SDK only forwards your API key.

Credentials travel in the ``Authorization`` header on both the REST calls and the WebSocket upgrade.
``websocket-client`` sets arbitrary upgrade headers, so the browser constraint that forces a
``?access_token=`` query parameter does not apply to this client. See ``token_in_query`` on
:class:`RealtimeAPI` for the legacy escape hatch.
"""
from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from typing import Any, Callable
from urllib.parse import quote, urlencode
from wave.client import WaveClient

import httpx

_DEFAULT_WS = "wss://realtime.wave.online"


def _http_origin(ws_url: str) -> str:
    """Derive the https REST origin from a (ws/wss) base URL."""
    base = ws_url.rstrip("/")
    if base.startswith("ws"):
        return "http" + base[2:]
    return base


def _channel_path(channel: str) -> str:
    """Percent-encode a channel for use as a single REST path segment.

    ``:`` stays literal because WAVE channel names are ``stream:abc`` shaped; everything else that
    could leave the segment (``/``, ``?``, ``#``, ``&``) is encoded.
    """
    return quote(channel, safe=":")


class RealtimeChannel:
    """One subscribed channel over a WebSocket.

    Iterate the channel for raw frames, or register ``.on(event, cb)`` handlers and call ``.run()``::

        ch = wave.realtime.connect("stream:abc")
        ch.on("transcription.partial", lambda data: print(data))
        ch.run()  # blocks, dispatching frames
    """

    def __init__(
        self,
        channel: str,
        api_key: str,
        ws_base: str = _DEFAULT_WS,
        as_: str | None = None,
        organization_id: str | None = None,
        token_in_query: bool = False,
    ):
        try:
            import websocket  # websocket-client (optional dep)
        except ImportError as e:  # pragma: no cover - import guard
            raise ImportError(
                "WAVE realtime requires the 'websocket-client' package: pip install 'wave-sdk[realtime]'"
            ) from e
        self.channel = channel

        # Every value is urlencoded: a channel containing '&' or '#' would otherwise inject or
        # truncate query parameters on the upgrade.
        params: dict[str, str] = {"channel": channel}
        if as_:
            params["as"] = as_

        headers = [f"Authorization: Bearer {api_key}"]
        if organization_id:
            headers.append(f"X-Organization-Id: {organization_id}")

        if token_in_query:
            # Legacy form for deployments that cannot read the upgrade header. The key lands in
            # proxy logs, edge access logs, and shell history — opt in deliberately or not at all.
            params["access_token"] = api_key

        url = f"{ws_base.rstrip('/')}/v1/connect?{urlencode(params)}"
        self._ws = websocket.create_connection(url, header=headers)
        self._handlers: dict[str, list[Callable[[Any], None]]] = {}

    def __iter__(self) -> Iterator[dict]:
        try:
            while True:
                raw = self._ws.recv()
                if not raw:
                    break
                yield json.loads(raw)
        except Exception:
            return

    def on(self, event: str, callback: Callable[[Any], None]) -> RealtimeChannel:
        """Register a handler. ``event`` is a frame type ('message','join','leave','presence') or a WAVE
        event name (e.g. 'caption.cue', 'sentiment.tick'). Returns self for chaining."""
        self._handlers.setdefault(event, []).append(callback)
        return self

    def run(self) -> None:
        """Block, dispatching frames to ``.on()`` handlers. Event-name handlers receive the event's data;
        type handlers receive the whole frame."""
        for frame in self:
            ftype = frame.get("type")
            if ftype == "message" and frame.get("event"):
                for cb in self._handlers.get(frame["event"], []):
                    cb(frame.get("data"))
            if ftype:
                for cb in self._handlers.get(ftype, []):
                    cb(frame)

    def send(self, event: str, data: Any = None) -> None:
        """Publish an event to this channel over the socket."""
        self._ws.send(json.dumps({"op": "publish", "event": event, "data": data}))

    def request_presence(self) -> None:
        self._ws.send(json.dumps({"op": "presence"}))

    def close(self) -> None:
        with contextlib.suppress(Exception):  # pragma: no cover
            self._ws.close()


class RealtimeAPI:
    """Realtime entry point. ``wave.realtime.connect('stream:abc')`` for WS; ``publish/presence/history``
    are one-shot REST calls for producers that don't hold a socket.

    ``token_in_query`` re-enables the legacy ``?access_token=`` upgrade parameter for a deployment
    that cannot read the ``Authorization`` header. It is off by default because a credential in a URL
    is recorded by every hop that logs the request line.
    """

    def __init__(self, client: WaveClient, url: str = _DEFAULT_WS, token_in_query: bool = False):
        self._api_key = client.api_key
        # Multi-tenant isolation: WaveClient stamps X-Organization-Id on every other surface, so
        # realtime carries it too — on the REST calls and on the WS upgrade.
        self._organization_id = client.organization_id
        self._ws_base = url.rstrip("/")
        self._http_base = _http_origin(self._ws_base)
        self._token_in_query = token_in_query

    def connect(self, channel: str, as_: str | None = None) -> RealtimeChannel:
        return RealtimeChannel(
            channel,
            self._api_key,
            self._ws_base,
            as_,
            organization_id=self._organization_id,
            token_in_query=self._token_in_query,
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._api_key}", "content-type": "application/json"}
        if self._organization_id:
            headers["X-Organization-Id"] = self._organization_id
        return headers

    def publish(self, channel: str, event: str, data: Any = None) -> dict:
        r = httpx.post(
            f"{self._http_base}/v1/channels/{_channel_path(channel)}/publish",
            headers=self._headers(),
            json={"event": event, "data": data},
        )
        return r.json()

    def presence(self, channel: str) -> dict:
        r = httpx.get(
            f"{self._http_base}/v1/channels/{_channel_path(channel)}/presence",
            headers=self._headers(),
        )
        return r.json()

    def history(self, channel: str, limit: int = 50) -> dict:
        r = httpx.get(
            f"{self._http_base}/v1/channels/{_channel_path(channel)}/history",
            headers=self._headers(),
            params={"limit": limit},
        )
        return r.json()
