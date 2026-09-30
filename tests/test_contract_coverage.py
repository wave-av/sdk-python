"""Contract test: every operation in the published WAVE OpenAPI document is either sent by a Python
SDK method, checked on the wire, or listed with a reason.

The snapshot (tests/fixtures/openapi_snapshot.json) is regenerated from
https://api.wave.online/openapi.json by ``python3 scripts/refresh_openapi_snapshot.py``. Paths in
it are relative to the spec's server URL, which ends in ``/v1``.

For every mapped operation the test calls the SDK method against an ``httpx.MockTransport`` and
asserts that the request it actually sends has the operation's HTTP verb and matches its templated
path. A method name that exists but sends a different path fails here; earlier versions of this
test only checked that the method name existed, which let 19 of 52 mapped methods drift.

Operations carrying ``x-skill-url`` are the single-call product invocation surface
(``POST /v1/<product>``, one per product); they are counted, not mapped one by one.
"""
from __future__ import annotations

import json
import re
import sys
import types
import warnings
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import Recorder, attach

SNAPSHOT = json.loads((Path(__file__).parent / "fixtures" / "openapi_snapshot.json").read_text())
OPERATIONS: list[dict[str, Any]] = SNAPSHOT["operations"]


def _op_key(op: dict[str, Any]) -> str:
    return op["operationId"] or f"{op['method']} {op['path']}"


SPEC = {_op_key(op): op for op in OPERATIONS}
SKILL_OPS = [op for op in OPERATIONS if op["skill_invocation"]]
API_OPS = {_op_key(op): op for op in OPERATIONS if not op["skill_invocation"]}

_MANIFEST = {
    "slug": "demo",
    "title": "Demo",
    "tiers": [{"id": "base", "name": "Base", "price_usdc_micro": "10000", "rail": "x402", "billing": "per_op", "features": []}],
}

# operation key -> (namespace, method, positional args, keyword args)
MAPPING: dict[str, tuple[str, str, tuple[Any, ...], dict[str, Any]]] = {
    "getAnalyticsEngagement": ("pulse", "get_engagement_metrics", (), {}),
    "getAnalyticsOverview": ("pulse", "get_overview", (), {}),
    "getAnalyticsTopContent": ("pulse", "get_top_content", (), {}),
    "listCaptions": ("captions", "list", (), {}),
    "createCaptionJob": ("captions", "generate", ("media_1",), {}),
    "getCaptionJob": ("captions", "get", ("job_1",), {}),
    "deleteCaptionJob": ("captions", "remove", ("job_1",), {}),
    "downloadCaptions": ("captions", "download", ("job_1", "en"), {"format": "srt"}),
    "listClips": ("clips", "list", (), {}),
    "createClip": ("clips", "create", ("Best moment", {"type": "stream", "id": "s1"}), {}),
    "detectClips": ("clips", "detect", ("video_1",), {}),
    "getClip": ("clips", "get", ("clip_1",), {}),
    "updateClip": ("clips", "update", ("clip_1",), {"title": "t"}),
    "deleteClip": ("clips", "remove", ("clip_1",), {}),
    "listCollabRooms": ("collab", "list_rooms", (), {}),
    "createCollabRoom": ("collab", "create_room", ("Room",), {}),
    "getCollabRoom": ("collab", "get_room", ("room_1",), {}),
    "deleteCollabRoom": ("collab", "delete_room", ("room_1",), {}),
    "createComposeProposal": ("compose", "compose", ("live captions for a webinar",), {}),
    "getComposeProposal": ("compose", "get_proposal", ("prp_1",), {}),
    "listProjects": ("editor", "list_projects", (), {}),
    "createProject": ("editor", "create_project", ("Cut",), {}),
    "getProject": ("editor", "get_project", ("prj_1",), {}),
    "updateProject": ("editor", "update_project", ("prj_1",), {"title": "t"}),
    "deleteProject": ("editor", "remove_project", ("prj_1",), {}),
    "exportProject": ("editor", "export", ("prj_1",), {"format": "mp4"}),
    "listCalls": ("phone", "list_calls", (), {}),
    "makeCall": ("phone", "make_call", ("+15550100", "+15550101"), {}),
    "listPodcastShows": ("podcast", "list", (), {}),
    "createPodcastShow": ("podcast", "create", ("Show",), {}),
    "listPodcastEpisodes": ("podcast", "list_episodes", ("show_1",), {}),
    "createPodcastEpisode": ("podcast", "create_episode", ("show_1", "Ep 1"), {"audio_url": "https://example.com/a.mp3"}),
    "pricingManifestsList": ("pricing", "list_manifests", (), {}),
    "pricingManifestsCreate": ("pricing", "create_manifest", (_MANIFEST,), {}),
    "listProductions": ("studio", "list", (), {}),
    "createProduction": ("studio", "create", ("Show",), {}),
    "getProduction": ("studio", "get", ("prod_1",), {}),
    "realtimeHistory": ("realtime", "history", ("stream:abc",), {}),
    "realtimePresence": ("realtime", "presence", ("stream:abc",), {}),
    "realtimePublish": ("realtime", "publish", ("stream:abc", "note"), {}),
    "realtimeConnect": ("realtime", "connect", ("stream:abc",), {}),
    "search": ("search", "search", ("product launch",), {}),
    "searchAnalytics": ("search", "get_analytics", (), {}),
    "searchIndex": ("search", "index_media", ("media_1",), {}),
    "searchDelete": ("search", "remove_from_index", ("media_1",), {}),
    "listSentimentAnalyses": ("sentiment", "list", (), {}),
    "createSentimentAnalysis": ("sentiment", "analyze", ("asset_1",), {}),
    "analyzeText": ("sentiment", "analyze_text", ("great show",), {}),
    "GET /streams": ("pipeline", "list", (), {}),
    "POST /streams": ("pipeline", "create", ("Main",), {}),
    "getStream": ("pipeline", "get", ("str_1",), {}),
    "startStream": ("pipeline", "start", ("str_1",), {}),
    "stopStream": ("pipeline", "stop", ("str_1",), {}),
    "listTranscriptions": ("transcribe", "list", (), {}),
    "createTranscription": ("transcribe", "create", ("https://example.com/a.mp3",), {}),
    "getTranscription": ("transcribe", "get", ("tr_1",), {}),
    "deleteTranscription": ("transcribe", "remove", ("tr_1",), {}),
    "GET /usage": ("usage", "get", (), {}),
    "listChapters": ("chapters", "list_chapters", ("video_1",), {}),
    "createChapter": ("chapters", "create_chapter", ("video_1", "Intro", 0, 30), {}),
    "detectChapters": ("chapters", "detect", ("video_1",), {}),
    "cloneVoice": ("voice", "clone_voice", ("Narrator", ["https://example.com/s.wav"]), {}),
    "generateSpeech": ("voice", "generate", ("hello", "voice_1"), {}),
    "listVoices": ("voice", "list_voices", (), {}),
}

_UNWRAPPED = "not wrapped by the Python SDK yet; callable with client.client.request(...)"

# operation key -> reason it has no mapped SDK method. Every API operation not in MAPPING must be
# listed here with a reason of at least 20 characters.
ALLOWLIST: dict[str, str] = {
    "agentAuthDevice": "the device-authorization ceremony for agents (RFC 8628); " + _UNWRAPPED,
    "agentAuthToken": "the token half of the agent device-authorization ceremony; " + _UNWRAPPED,
    "avDemux": _UNWRAPPED,
    "avRemux": _UNWRAPPED,
    "batchOperations": "generic batch envelope; " + _UNWRAPPED,
    "getBilling": _UNWRAPPED,
    "getBillingUsage": "billing view of usage; client.usage.get() wraps GET /v1/usage. " + _UNWRAPPED,
    "publishBraidAudio": _UNWRAPPED,
    "stopBraidAudio": _UNWRAPPED,
    "listCameras": _UNWRAPPED,
    "registerCamera": _UNWRAPPED,
    "controlCamera": _UNWRAPPED,
    "runComposeProposal": "executes a proposal (billed work); ComposeAPI is deliberately "
        "propose-only and never executes. " + _UNWRAPPED,
    "custodyOperation": _UNWRAPPED,
    "engineCapabilities": _UNWRAPPED,
    "gpuStatus": _UNWRAPPED,
    "gpuInfer": _UNWRAPPED,
    "identityResolve": _UNWRAPPED,
    "GET /leaderboard": "public leaderboard (no operationId in the spec); " + _UNWRAPPED,
    "transcribeLiveAudio": _UNWRAPPED,
    "startLivePipeline": _UNWRAPPED,
    "moderateContent": _UNWRAPPED,
    "mintMoqPublishToken": "Media over QUIC publish token; " + _UNWRAPPED,
    "mintMoqSubscribeToken": "Media over QUIC subscribe token; " + _UNWRAPPED,
    "listPhoneLines": "the phone API serves numbers under /v1/phone/numbers, which PhoneAPI "
        "wraps; the published /phone/lines path is not the served one, so no method sends it",
    "provisionPhoneLine": "see listPhoneLines; PhoneAPI.purchase_number sends POST "
        "/v1/phone/numbers, the served provisioning route",
    "GET /platform": "platform descriptor (no operationId in the spec); " + _UNWRAPPED,
    "switchProductionCamera": _UNWRAPPED,
    "setProductionOverlay": _UNWRAPPED,
    "renderVideo": "standalone render service; " + _UNWRAPPED,
    "renderPoll": "standalone render service; " + _UNWRAPPED,
    "renderEvents": "standalone render service; " + _UNWRAPPED,
    "getStreamAnalytics": _UNWRAPPED,
    "listStreamHighlights": _UNWRAPPED,
    "markStreamHighlight": _UNWRAPPED,
    "getStreamStatus": _UNWRAPPED,
    "listEnhancements": "StudioAIAPI predates the enhancements resource; " + _UNWRAPPED,
    "createEnhancement": "StudioAIAPI predates the enhancements resource; " + _UNWRAPPED,
    "previewEnhancement": "StudioAIAPI predates the enhancements resource; " + _UNWRAPPED,
}


def _path_regex(template: str) -> re.Pattern[str]:
    return re.compile("^/v1" + re.sub(r"\{[^}]+\}", "[^/]+", template) + "$")


class _FakeSocket:
    def recv(self) -> str:
        return ""

    def close(self) -> None:
        pass


def _send(monkeypatch: pytest.MonkeyPatch, namespace: str, method: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[str, str]:
    """Call one SDK method and return the (verb, path) of the request it sent."""
    from wave_sdk import Wave

    recorder = Recorder()
    wave = Wave(api_key="test-api-key", organization_id="org_test")
    attach(wave.client, recorder)
    monkeypatch.setattr("wave_sdk.client.time.sleep", lambda _s: None)

    upgrades: list[str] = []
    fake_ws = types.ModuleType("websocket")
    fake_ws.create_connection = lambda url, header=None, **_k: upgrades.append(url) or _FakeSocket()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "websocket", fake_ws)

    call = getattr(getattr(wave, namespace), method)
    if namespace == "pricing" and method == "create_manifest":
        from wave_sdk.pricing import PricingManifest

        args = (PricingManifest(**args[0]),)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        try:
            call(*args, **kwargs)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            # The mock answers `{}`; a response model may reject it after the request was sent.
            if not recorder.requests and not upgrades:
                raise AssertionError(f"{namespace}.{method} raised before sending: {exc!r}") from exc

    if upgrades:
        from urllib.parse import urlsplit

        return "GET", urlsplit(upgrades[-1]).path
    assert len(recorder.requests) == 1, f"{namespace}.{method} sent {len(recorder.requests)} requests"
    req = recorder.last
    return req.method, req.url.path


def test_snapshot_is_sane():
    """Guard against an empty or truncated fixture silently passing everything."""
    assert SNAPSHOT["total_ops"] == len(OPERATIONS) >= 250
    assert SNAPSHOT["servers"] and SNAPSHOT["servers"][0].rstrip("/").endswith("/v1")
    keys = [_op_key(op) for op in OPERATIONS]
    assert len(keys) == len(set(keys)), "duplicate operation keys in the snapshot"


def test_skill_invocation_ops_are_single_product_posts():
    shapes = {(op["method"], op["path"].count("/")) for op in SKILL_OPS}
    assert shapes == {("POST", 1)}, f"unexpected skill-invocation op shapes: {shapes}"
    assert len(SKILL_OPS) >= 100


def test_every_api_op_is_mapped_or_allowlisted():
    unmapped = sorted(k for k in API_OPS if k not in MAPPING and k not in ALLOWLIST)
    assert not unmapped, (
        f"{len(unmapped)} spec operation(s) have no Python method and no allowlist reason: {unmapped}"
    )
    stubs = [k for k, v in ALLOWLIST.items() if len(v) < 20]
    assert not stubs, f"allowlist entries missing a real reason: {stubs}"
    assert not set(MAPPING) & set(ALLOWLIST), "an operation is both mapped and allowlisted"


def test_no_stale_mapping_or_allowlist_entries():
    stale = (set(MAPPING) | set(ALLOWLIST)) - set(API_OPS)
    assert not stale, f"entries reference operations no longer in the spec: {sorted(stale)}"


@pytest.mark.parametrize("op_key", sorted(MAPPING))
def test_mapped_method_sends_the_spec_operation(op_key: str, monkeypatch: pytest.MonkeyPatch):
    namespace, method, args, kwargs = MAPPING[op_key]
    op = SPEC[op_key]
    verb, path = _send(monkeypatch, namespace, method, args, kwargs)
    expected = f"{op['method']} /v1{op['path']}"
    assert verb == op["method"], f"wave.{namespace}.{method} sent {verb} {path}; spec is {expected}"
    assert _path_regex(op["path"]).match(path), f"wave.{namespace}.{method} sent {verb} {path}; spec is {expected}"
