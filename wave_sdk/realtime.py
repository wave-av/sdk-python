"""WAVE SDK - Realtime API.

The WAVE Realtime control & event plane: presence, pub/sub broadcast, and the streaming-event bus
the WAVE AI products push into. Subscribe once to a channel and receive live transcription /
captions / sentiment / clip / stream events with no polling.

Everything goes through the API host (``https://api.wave.online``):

* REST: ``POST /v1/realtime/channels/{channel}/publish``, ``GET .../presence``, ``GET .../history``
  (sent through :class:`~wave_sdk.client.WaveClient`, so they carry ``X-Organization-Id`` and
  raise :class:`~wave_sdk.client.WaveError` on failure like every other namespace);
* WebSocket: ``wss://api.wave.online/v1/realtime/connect?channel=...``.

WebSocket support uses the optional ``websocket-client`` package: ``pip install 'wave-sdk[realtime]'``.
Credentials travel only in the ``Authorization`` header, on the REST calls and on the WebSocket
upgrade alike. ``websocket-client`` sets arbitrary upgrade headers, so the browser constraint that
forces a ``?access_token=`` query parameter does not apply here, and the SDK never puts the key in
a URL (a URL is recorded by every proxy and edge log that sees the request line).
"""
from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from typing import Any, Callable
from urllib.parse import quote, urlencode

import httpx

from wave_sdk.client import WaveClient, WaveError, __version__, error_from_response

_DEFAULT_WS = "wss://api.wave.online"
_CONNECT_PATH = "/v1/realtime/connect"
_CHANNELS_PATH = "/v1/realtime/channels"


def _ws_origin(http_url: str) -> str:
    """Derive the ws(s) origin from an http(s) base URL (``https://api.wave.online`` -> ``wss://...``)."""
    base = http_url.rstrip("/")
    if base.startswith("https://"):
        return "wss://" + base[len("https://"):]
    if base.startswith("http://"):
        return "ws://" + base[len("http://"):]
    return base


def _channel_path(channel: str) -> str:
    """Percent-encode a channel for use as a single REST path segment.

    ``:`` stays literal because WAVE channel names are ``stream:abc`` shaped (the API answers
    404 for ``stream%3Aabc``); everything else that could leave the segment (``/``, ``?``, ``#``,
    ``&``) is encoded.
    """
    return quote(channel, safe=":")


def _handshake_error(exc: Exception) -> WaveError | None:
    """Turn a rejected WebSocket upgrade (websocket-client's WebSocketBadStatusException) into the
    same WaveError subclass the REST path raises for that status and body."""
    status = getattr(exc, "status_code", None)
    if not isinstance(status, int):
        return None
    body = getattr(exc, "resp_body", None) or b""
    if isinstance(body, str):
        body = body.encode()
    headers = getattr(exc, "resp_headers", None) or {}
    try:
        response = httpx.Response(status, content=body, headers=dict(headers))
    except Exception:  # pragma: no cover - defensive: malformed handshake headers
        response = httpx.Response(status, content=body)
    return error_from_response(response)


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

        headers = [f"Authorization: Bearer {api_key}", f"User-Agent: wave-sdk-python/{__version__}"]
        if organization_id:
            headers.append(f"X-Organization-Id: {organization_id}")

        url = f"{ws_base.rstrip('/')}{_CONNECT_PATH}?{urlencode(params)}"
        try:
            self._ws = websocket.create_connection(url, header=headers)
        except Exception as e:
            error = _handshake_error(e)
            if error is not None:
                raise error from e
            raise
        self._handlers: dict[str, list[Callable[[Any], None]]] = {}

    def __iter__(self) -> Iterator[dict[str, Any]]:
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

    ``url`` overrides the WebSocket origin (default: the client's ``base_url`` with ``https``
    swapped for ``wss``); the connect path ``/v1/realtime/connect`` is appended to it.
    """

    def __init__(self, client: WaveClient, url: str | None = None):
        self._client = client
        self._api_key = client.api_key
        # Multi-tenant isolation: WaveClient stamps X-Organization-Id on every REST call, so the
        # WebSocket upgrade carries it too.
        self._organization_id = client.organization_id
        self._ws_base = (url or _ws_origin(client.base_url)).rstrip("/")

    def connect(self, channel: str, as_: str | None = None) -> RealtimeChannel:
        """Open ``wss://…/v1/realtime/connect?channel=…``. A rejected upgrade raises the same
        :class:`~wave_sdk.client.WaveError` subclass a REST call would for that status and body."""
        return RealtimeChannel(
            channel, self._api_key, self._ws_base, as_, organization_id=self._organization_id
        )

    def publish(self, channel: str, event: str, data: Any = None) -> dict[str, Any]:
        """``POST /v1/realtime/channels/{channel}/publish`` (scope ``realtime:write``)."""
        result: dict[str, Any] = self._client.post(
            f"{_CHANNELS_PATH}/{_channel_path(channel)}/publish", json={"event": event, "data": data}
        )
        return result

    def presence(self, channel: str) -> dict[str, Any]:
        """``GET /v1/realtime/channels/{channel}/presence``."""
        result: dict[str, Any] = self._client.get(f"{_CHANNELS_PATH}/{_channel_path(channel)}/presence")
        return result

    def history(self, channel: str, limit: int = 50) -> dict[str, Any]:
        """``GET /v1/realtime/channels/{channel}/history`` (the API caps ``limit`` at 50)."""
        result: dict[str, Any] = self._client.get(
            f"{_CHANNELS_PATH}/{_channel_path(channel)}/history", params={"limit": limit}
        )
        return result
