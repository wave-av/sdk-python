"""Contract test: every operation in the live WAVE OpenAPI spec has a Python
SDK method, or is explicitly allowlisted with a justification.

The spec snapshot (tests/fixtures/openapi_snapshot.json) is a point-in-time
capture of https://api.wave.online/openapi.json (75 ops across 54 paths,
fetched 2026-09-01). Re-fetch and regenerate the snapshot when the live spec
grows; this test fails loud if new operations appear unmapped and unallowed.

Two allowlist classes, both justified inline:
  - "unwrapped": a genuinely new backend surface neither the TypeScript nor
    the Python SDK wraps yet (verified by grep against @wave-av/sdk
    origin/main). Not part of this pass's TS-namespace-parity scope.
  - "drift": the namespace exists in both SDKs, but the concrete method the
    spec describes was never implemented on either side (pre-existing drift,
    predates this task).
"""
from __future__ import annotations

import json
from pathlib import Path

SNAPSHOT = json.loads((Path(__file__).parent / "fixtures" / "openapi_snapshot.json").read_text())


def _op_key(op: dict) -> str:
    return op["operationId"] or f"{op['method']} {op['path']}"


# operationId (or "METHOD /path" when the spec omits an operationId) -> (namespace, method)
MAPPING: dict[str, tuple[str, str]] = {
    "listCaptions": ("captions", "list"),
    "createCaptionJob": ("captions", "generate"),
    "getCaptionJob": ("captions", "get"),
    "deleteCaptionJob": ("captions", "remove"),
    "downloadCaptions": ("captions", "get_text"),
    "listClips": ("clips", "list"),
    "createClip": ("clips", "create"),
    "detectClips": ("clips", "detect_highlights"),
    "getClip": ("clips", "get"),
    "updateClip": ("clips", "update"),
    "deleteClip": ("clips", "remove"),
    "listCollabRooms": ("collab", "list_rooms"),
    "createCollabRoom": ("collab", "create_room"),
    "getCollabRoom": ("collab", "get_room"),
    "deleteCollabRoom": ("collab", "close_room"),
    "listProjects": ("editor", "list_projects"),
    "createProject": ("editor", "create_project"),
    "getProject": ("editor", "get_project"),
    "updateProject": ("editor", "update_project"),
    "deleteProject": ("editor", "remove_project"),
    "exportProject": ("editor", "render"),
    "listCalls": ("phone", "list_calls"),
    "makeCall": ("phone", "make_call"),
    "listPhoneLines": ("phone", "list_numbers"),
    "provisionPhoneLine": ("phone", "purchase_number"),
    "listPodcastShows": ("podcast", "list"),
    "createPodcastShow": ("podcast", "create"),
    "listPodcastEpisodes": ("podcast", "list_episodes"),
    "createPodcastEpisode": ("podcast", "create_episode"),
    "pricingManifestsList": ("pricing", "list_manifests"),
    "pricingManifestsCreate": ("pricing", "create_manifest"),
    "realtimeHistory": ("realtime", "history"),
    "realtimePresence": ("realtime", "presence"),
    "realtimePublish": ("realtime", "publish"),
    "realtimeConnect": ("realtime", "connect"),
    "search": ("search", "search"),
    "searchAnalytics": ("search", "get_analytics"),
    "searchIndex": ("search", "index_media"),
    "searchDelete": ("search", "remove_from_index"),
    "listSentimentAnalyses": ("sentiment", "list"),
    "createSentimentAnalysis": ("sentiment", "analyze"),
    "analyzeText": ("sentiment", "analyze_text"),
    "listTranscriptions": ("transcribe", "list"),
    "createTranscription": ("transcribe", "create"),
    "getTranscription": ("transcribe", "get"),
    "deleteTranscription": ("transcribe", "remove"),
    "listChapters": ("chapters", "get_default_set"),
    "createChapter": ("chapters", "add_chapter"),
    "detectChapters": ("chapters", "generate"),
    "cloneVoice": ("voice", "clone_voice"),
    "generateSpeech": ("voice", "synthesize"),
    "listVoices": ("voice", "list_voices"),
}

# operationId (or "METHOD /path") -> justification. Every spec op not in MAPPING must be here.
ALLOWLIST: dict[str, str] = {
    "agentAuthDevice": "TS implements the RFC 8628 ceremony as standalone module functions "
        "(startAgentCeremony et al in agent-auth.ts), not a Wave facade namespace — out of "
        "scope for this namespace-parity pass.",
    "agentAuthToken": "see agentAuthDevice — same standalone TS ceremony surface.",
    "avDemux": "unwrapped by either SDK (verified: no av/demux reference in @wave-av/sdk "
        "origin/main src/*.ts) — new backend surface, not part of TS-namespace parity.",
    "avRemux": "unwrapped by either SDK — see avDemux.",
    "batchOperations": "the top-level /batch op is unwrapped; qr.ts and sentiment.ts call "
        "their own namespaced .../batch sub-resource endpoints, not this generic op.",
    "publishBraidAudio": "unwrapped by either SDK (verified: no braid/publish reference in "
        "@wave-av/sdk origin/main) — new backend surface.",
    "stopBraidAudio": "unwrapped by either SDK — see publishBraidAudio.",
    "custodyOperation": "TS wraps this as a standalone CustodyClient (custody.ts), not a "
        "Wave facade namespace — out of scope for this namespace-parity pass.",
    "engineCapabilities": "unwrapped by either SDK — new backend surface.",
    "gpuInfer": "unwrapped by either SDK — new backend surface.",
    "gpuStatus": "unwrapped by either SDK — see gpuInfer.",
    "identityResolve": "unwrapped by either SDK — new backend surface.",
    "GET /leaderboard": "unwrapped by either SDK; the spec omits an operationId for this op.",
    "mintMoqPublishToken": "unwrapped by either SDK — new backend surface (Media over QUIC).",
    "mintMoqSubscribeToken": "unwrapped by either SDK — see mintMoqPublishToken.",
    "GET /platform": "unwrapped by either SDK; the spec omits an operationId for this op.",
    "renderVideo": "the standalone render service is listed as phase=\"planned\" in TS "
        "products.ts's catalog, not implemented as an SDK call by either SDK.",
    "renderPoll": "unwrapped by either SDK — see renderVideo.",
    "renderEvents": "unwrapped by either SDK — see renderVideo.",
    "GET /usage": "unwrapped top-level org-usage op; inference.ts and prompter.ts only call "
        "their own namespaced usage sub-paths, not this endpoint. Spec omits an operationId.",
    "listEnhancements": "studio-ai namespace exists in both SDKs, but neither implements the "
        "literal enhancements CRUD the spec describes — pre-existing drift, predates this task.",
    "createEnhancement": "see listEnhancements — same pre-existing studio-ai drift.",
    "previewEnhancement": "see listEnhancements — same pre-existing studio-ai drift.",
}


def test_snapshot_is_sane():
    """Guard against an empty/corrupt fixture silently passing everything."""
    assert SNAPSHOT["total_ops"] == len(SNAPSHOT["operations"]) == 75


def test_every_op_is_mapped_or_allowlisted():
    keys = [_op_key(op) for op in SNAPSHOT["operations"]]
    unmapped = [k for k in keys if k not in MAPPING and k not in ALLOWLIST]
    assert not unmapped, (
        f"{len(unmapped)} spec operation(s) have no Python method and no allowlist "
        f"justification: {unmapped}"
    )
    # Every allowlist entry must carry a real justification (not a stub).
    stubs = [k for k, v in ALLOWLIST.items() if len(v) < 20]
    assert not stubs, f"allowlist entries missing a real justification: {stubs}"


def test_no_stale_mapping_or_allowlist_entries():
    keys = {_op_key(op) for op in SNAPSHOT["operations"]}
    stale_mapped = set(MAPPING) - keys
    stale_allowed = set(ALLOWLIST) - keys
    assert not stale_mapped, f"MAPPING references ops no longer in the spec: {stale_mapped}"
    assert not stale_allowed, f"ALLOWLIST references ops no longer in the spec: {stale_allowed}"


def test_mapped_methods_exist_on_wave():
    from wave_sdk import Wave
    w = Wave(api_key="test-key")
    missing = []
    for op_id, (namespace, method) in MAPPING.items():
        ns = getattr(w, namespace, None)
        if ns is None or not hasattr(ns, method):
            missing.append(f"{op_id} -> wave.{namespace}.{method}")
    assert not missing, f"mapped spec operations missing their Python method: {missing}"


def test_mapping_and_allowlist_cover_every_op_exactly_once():
    keys = [_op_key(op) for op in SNAPSHOT["operations"]]
    assert len(keys) == len(set(keys)), "duplicate operation keys in the snapshot"
    covered = set(MAPPING) | set(ALLOWLIST)
    assert covered == set(keys)
    assert len(MAPPING) + len(ALLOWLIST) == SNAPSHOT["total_ops"]
