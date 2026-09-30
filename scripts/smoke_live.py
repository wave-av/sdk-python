"""Live smoke test: run the SDK's documented flows against the real WAVE API.

    WAVE_API_KEY=... python3 scripts/smoke_live.py

Every call is a free read, a proposal that never executes, a request the API rejects before any
work is done (an unsupported model name), or one realtime event published to the
``stream:sdk-smoke`` channel (only when the key holds ``realtime:write``), so a run costs nothing.
The script prints one line per check with the HTTP outcome and the request id. It never prints the
key or a response body.

Each check says what it expects:

* ``200``: the flow must succeed and parse into the SDK's model;
* ``error CODE``: the API must answer with that error code, parsed into the named WaveError
  subclass (this proves the request reached a real route with a working key and that the SDK
  surfaces the server's code and message);
* a list: any one of the outcomes it holds.

A GET to ``/v1/network/surface`` runs first as a control: a route that is known to be served. If it
fails, the key or the network is at fault, and no other result means anything.

Exit status: 0 when every check matches its expectation, 1 otherwise, 2 when WAVE_API_KEY is unset.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any, Callable

from wave_sdk import PaymentRequiredError, RouteNotServedError, Wave, WaveError

Check = tuple[str, Callable[[Wave], Any], Any]


# x-request-id of the most recent HTTP response, so a 200 line carries the same receipt an error does.
_LAST_RID: dict[str, str] = {}


def _remember_request_id(response: Any) -> None:
    _LAST_RID["rid"] = response.headers.get("x-request-id") or "-"


def _request_id(obj: Any) -> str:
    return getattr(obj, "request_id", None) or "-"


def _checks() -> list[Check]:
    channel = "stream:sdk-smoke"
    return [
        ("control GET /v1/network/surface", lambda w: w.client.get("/v1/network/surface"), 200),
        ("usage.get", lambda w: w.usage.get(), 200),
        ("search.search", lambda w: w.search.search(query="product launch"), 200),
        ("search.get_analytics", lambda w: w.search.get_analytics(), 200),
        ("pricing.list_manifests", lambda w: w.pricing.list_manifests(), 200),
        ("compose.compose", lambda w: w.compose.compose("live captions for tomorrow's webinar"), 200),
        ("pulse.get_overview", lambda w: w.pulse.get_overview(), 200),
        ("pulse.get_top_content", lambda w: w.pulse.get_top_content(limit=5), 200),
        ("pulse.get_engagement_metrics", lambda w: w.pulse.get_engagement_metrics(), 200),
        ("meter.ledger", lambda w: w.meter.ledger(), 200),
        ("meter.rollup", lambda w: w.meter.rollup(), 200),
        ("realtime.presence", lambda w: w.realtime.presence(channel), 200),
        ("realtime.history", lambda w: w.realtime.history(channel, limit=1), 200),
        # publish needs realtime:write. A key without it must get the gateway's scope error for
        # this exact route (proof the request reached it), never a transport failure.
        (
            "realtime.publish",
            lambda w: w.realtime.publish(channel, "sdk.smoke", {"ok": True}),
            [200, (WaveError, "SCOPE_INSUFFICIENT")],
        ),
        ("inference.models", lambda w: w.inference.models(), 200),
        (
            "inference.complete (unsupported model)",
            lambda w: w.inference.complete("sdk-smoke-unsupported-model", [{"role": "user", "content": "hi"}], max_tokens=1),
            (WaveError, "model_not_supported"),
        ),
        ("mesh.list_peers", lambda w: w.mesh.list_peers(node="sdk-smoke"), 200),
    ]


def _outcome_matches(expected: Any, result: Any, error: WaveError | None) -> bool:
    if isinstance(expected, list):  # any one of several acceptable outcomes
        return any(_outcome_matches(e, result, error) for e in expected)
    if expected == 200:
        return error is None
    cls, code = expected
    return isinstance(error, cls) and error.code == code


def _describe(result: Any, error: WaveError | None, elapsed: float) -> str:
    if error is not None:
        kind = type(error).__name__
        return f"{kind} {error.status_code} {error.code} rid={_request_id(error)} ({elapsed:.1f}s)"
    shape = type(result).__name__
    return f"200 -> {shape} rid={_LAST_RID.get('rid', '-')} ({elapsed:.1f}s)"


def _run(wave: Wave, name: str, fn: Callable[[Wave], Any], expected: Any) -> bool:
    _LAST_RID.clear()
    started = time.monotonic()
    result: Any = None
    error: WaveError | None = None
    try:
        result = fn(wave)
    except WaveError as exc:
        error = exc
    except Exception as exc:  # a parsing or transport failure is a failed check, not a crash
        print(f"FAIL  {name}: {type(exc).__name__}: {str(exc)[:200]}")
        return False
    ok = _outcome_matches(expected, result, error)
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {_describe(result, error, time.monotonic() - started)}")
    return ok


def _websocket_check(wave: Wave) -> bool | None:
    """Open and close a realtime WebSocket, if the optional websocket-client package is installed."""
    try:
        import websocket  # noqa: F401
    except ImportError:
        print("SKIP  realtime.connect: pip install 'wave-sdk[realtime]' to include it")
        return None
    started = time.monotonic()
    try:
        channel = wave.realtime.connect("stream:sdk-smoke")
    except WaveError as exc:
        print(f"FAIL  realtime.connect: {_describe(None, exc, time.monotonic() - started)}")
        return False
    except Exception as exc:
        print(f"FAIL  realtime.connect: {type(exc).__name__}: {str(exc)[:200]}")
        return False
    channel.close()
    print(f"PASS  realtime.connect: upgraded and closed ({time.monotonic() - started:.1f}s)")
    return True


def _report_known_server_gaps(wave: Wave) -> None:
    """Informational: flows whose SDK request matches the published API but that the server does
    not answer yet. They are printed, not scored, so a server-side fix shows up here first."""
    probes: list[tuple[str, Callable[[Wave], Any]]] = [
        ("pipeline.list", lambda w: w.pipeline.list()),
        ("podcast.list", lambda w: w.podcast.list()),
        ("clips.list", lambda w: w.clips.list(limit=1)),
    ]
    for name, fn in probes:
        started = time.monotonic()
        try:
            fn(wave)
            print(f"INFO  {name}: 200 ({time.monotonic() - started:.1f}s)")
        except (RouteNotServedError, PaymentRequiredError, WaveError) as exc:
            print(f"INFO  {name}: {_describe(None, exc, time.monotonic() - started)}")


def main() -> int:
    api_key = os.environ.get("WAVE_API_KEY")
    if not api_key:
        print("WAVE_API_KEY is not set", file=sys.stderr)
        return 2
    base_url = os.environ.get("WAVE_BASE_URL", "https://api.wave.online")
    wave = Wave(api_key=api_key, base_url=base_url, max_retries=0)
    wave.client._client.event_hooks["response"].append(_remember_request_id)
    print(f"wave-sdk live smoke against {base_url}")

    checks = _checks()
    control_ok = _run(wave, *checks[0])
    if not control_ok:
        print("control failed: the key or the network is at fault; stopping", file=sys.stderr)
        return 1
    results = [_run(wave, *c) for c in checks[1:]]
    ws = _websocket_check(wave)
    if ws is not None:
        results.append(ws)
    _report_known_server_gaps(wave)

    passed = sum(results)
    print(f"{passed}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
