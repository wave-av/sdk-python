"""The requests each changed method actually sends, checked at the HTTP transport, and the live
response bodies (tests/fixtures/live_responses.json, recorded from https://api.wave.online with
ids scrubbed) parsing into the SDK's models."""
from __future__ import annotations

import json
from datetime import date

import httpx
import pytest

from tests.conftest import live, live_response
from wave_sdk.meter import MeterLedger, MeterRollup


def sent(recorder) -> tuple[str, str]:
    req = recorder.last
    return req.method, req.url.raw_path.decode()


def body(recorder) -> dict:
    return json.loads(recorder.last.content)


# --- usage --------------------------------------------------------------------------------------


def test_usage_get_parses_the_live_body(wave, recorder):
    recorder.set(lambda _r: live_response("usage"))
    report = wave.usage.get()
    assert sent(recorder) == ("GET", "/v1/usage")
    assert report.org == "org_fixture"
    assert report.range.days >= 1
    assert all(isinstance(v, float) for v in report.totals.values())


def test_usage_window_accepts_dates_and_strings(wave, recorder):
    recorder.set(lambda _r: live_response("usage"))
    wave.usage.get(from_=date(2026, 9, 1), to="2026-09-28")
    assert sent(recorder) == ("GET", "/v1/usage?from=20260901&to=20260928")


# --- pulse (analytics) ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method, label, path",
    [
        ("get_overview", "analytics_overview", "/v1/analytics/overview"),
        ("get_top_content", "analytics_top_content", "/v1/analytics/top-content"),
    ],
)
def test_pulse_published_reads(wave, recorder, method, label, path):
    recorder.set(lambda _r: live_response(label))
    result = getattr(wave.pulse, method)()
    assert sent(recorder) == ("GET", path)
    assert result["organizationId"] == "org_fixture"


def test_pulse_window_and_limit(wave, recorder):
    wave.pulse.get_top_content(from_="2026-09-01T00:00:00Z", limit=5)
    assert sent(recorder) == ("GET", "/v1/analytics/top-content?from=2026-09-01T00%3A00%3A00Z&limit=5")
    wave.pulse.get_engagement_metrics()
    assert sent(recorder) == ("GET", "/v1/analytics/engagement")


# --- meter ---------------------------------------------------------------------------------------


def test_meter_ledger_parses_the_live_window(wave, recorder):
    recorder.set(lambda _r: live_response("meter_ledger"))
    ledger = wave.meter.ledger()
    assert isinstance(ledger, MeterLedger)
    assert sent(recorder) == ("GET", "/v1/meter/ledger")
    assert ledger.org == "org_fixture"
    assert ledger.channels.sms is not None and ledger.channels.sms.blocked == "a2p-unregistered"
    assert ledger.channels.mail is not None and ledger.channels.mail.blocked == "mail_audit_not_owner"


def test_meter_rollup_parses_the_live_totals(wave, recorder):
    recorder.set(lambda _r: live_response("meter_rollup"))
    rollup = wave.meter.rollup()
    assert isinstance(rollup, MeterRollup)
    assert rollup.period == "month"
    assert rollup.totals.sms is not None and isinstance(rollup.totals.sms.blocked, str)


def test_meter_accepts_counts_and_unknown_fields():
    ledger = MeterLedger.model_validate({
        "org": "o", "from": "a", "to": "b", "generated_at": "c",
        "channels": {"sms": {"ops": 2, "blocked": 1}, "fax": {"pages": 3}},
    })
    assert ledger.channels.sms is not None and ledger.channels.sms.blocked == 1


def test_meter_missing_counters_are_none_not_zero():
    """A counter the response leaves out must not read as zero usage."""
    ledger = MeterLedger.model_validate({
        "org": "o", "from": "a", "to": "b", "generated_at": "c",
        "channels": {"voice": {"usdc": "0.25"}, "mail": {"ops": 4}},
    })
    assert ledger.channels.voice is not None and ledger.channels.voice.minutes is None
    assert ledger.channels.mail is not None and ledger.channels.mail.usdc is None
    assert ledger.channels.storage is None


# --- inference -----------------------------------------------------------------------------------


def test_inference_models_through_the_gateway(wave, recorder):
    recorder.set(lambda _r: live_response("inference_models"))
    models = wave.inference.models()
    assert sent(recorder) == ("GET", "/v1/inference/models")
    assert [m.id for m in models] == ["model-a", "model-b", "model-c"]


def test_inference_complete_through_the_gateway(wave, recorder):
    recorder.set(lambda _r: httpx.Response(200, json={"model": "m", "choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 3}}))
    result = wave.inference.complete("m", [{"role": "user", "content": "hi"}], max_tokens=1)
    assert sent(recorder) == ("POST", "/v1/inference/chat/completions")
    assert recorder.last.headers["authorization"] == "Bearer test-api-key"
    assert result.content == "ok"


# --- mesh ----------------------------------------------------------------------------------------


def test_mesh_requires_a_node_before_sending(wave, recorder):
    with pytest.raises(ValueError, match="x-wave-node"):
        wave.mesh.list_peers()
    assert recorder.requests == []


def test_mesh_sends_the_node_header(wave, recorder):
    recorder.set(lambda _r: live_response("mesh_peers"))
    wave.mesh.node = "studio-a"
    peers = wave.mesh.list_peers()
    assert sent(recorder) == ("GET", "/v1/mesh/peers")
    assert recorder.last.headers["x-wave-node"] == "studio-a"
    assert peers == {"count": 0, "org": "org_fixture", "peers": []}
    wave.mesh.list_peers(node="studio-b")
    assert recorder.last.headers["x-wave-node"] == "studio-b"


# --- path corrections ------------------------------------------------------------------------------


def test_sentiment_analyze_text_uses_the_published_path(wave, recorder):
    wave.sentiment.analyze_text("great show", include_emotions=True)
    assert sent(recorder) == ("POST", "/v1/sentiment/analyze")
    assert body(recorder) == {"text": "great show", "includeEmotions": True}


def test_clips_detect(wave, recorder):
    wave.clips.detect("vid_1", max_clips=3)
    assert sent(recorder) == ("POST", "/v1/clips/detect")
    assert body(recorder) == {"videoId": "vid_1", "maxClips": 3}


def test_voice_generate_returns_json_or_audio(wave, recorder):
    recorder.set(lambda _r: httpx.Response(200, json={"id": "gen_1"}))
    assert wave.voice.generate("hello", "voice_1", output_format="mp3_44100_128") == {"id": "gen_1"}
    assert sent(recorder) == ("POST", "/v1/voice/generate")
    assert body(recorder) == {"text": "hello", "voiceId": "voice_1", "outputFormat": "mp3_44100_128"}
    recorder.set(lambda _r: httpx.Response(200, content=b"ID3audio", headers={"content-type": "audio/mpeg"}))
    assert wave.voice.generate("hello", "voice_1") == b"ID3audio"


def test_captions_download(wave, recorder):
    recorder.set(lambda _r: httpx.Response(200, json={"url": "https://cdn.example.com/c.vtt"}))
    assert wave.captions.download("job_1", language="en", format="vtt") == {"url": "https://cdn.example.com/c.vtt"}
    assert sent(recorder) == ("GET", "/v1/captions/job_1/download?language=en&format=vtt")


def test_captions_download_keeps_a_file_body(wave, recorder):
    """If the API answers with the caption file itself, its text is returned, not dropped."""
    vtt = "WEBVTT\n\n00:00.000 --> 00:01.000\nhello\n"
    recorder.set(lambda _r: httpx.Response(200, text=vtt, headers={"content-type": "text/vtt; charset=utf-8"}))
    result = wave.captions.download("job_1", language="en", format="vtt")
    assert result == {"content": vtt, "content_type": "text/vtt; charset=utf-8"}


def test_chapters_per_video_operations(wave, recorder):
    wave.chapters.list_chapters("rec:1")
    assert sent(recorder) == ("GET", "/v1/videos/rec:1/chapters")
    wave.chapters.create_chapter("rec:1", "Intro", 0, 30.5)
    assert sent(recorder) == ("POST", "/v1/videos/rec:1/chapters")
    assert body(recorder) == {"title": "Intro", "startTime": 0, "endTime": 30.5}
    wave.chapters.detect("rec:1", max_chapters=4)
    assert sent(recorder) == ("POST", "/v1/videos/rec:1/chapters/detect")
    assert body(recorder) == {"maxChapters": 4}


def test_chapters_detect_sends_the_published_request_body(wave, recorder):
    """ChapterDetectRequest uses camelCase keys; an argument left as None is not sent."""
    wave.chapters.detect("rec:1", min_duration=45.0, max_chapters=6, include_descriptions=False, include_thumbnails=True)
    assert body(recorder) == {"minDuration": 45.0, "maxChapters": 6, "includeDescriptions": False, "includeThumbnails": True}
    wave.chapters.detect("rec:1", include_thumbnails=False)
    assert body(recorder) == {"includeThumbnails": False}
    wave.chapters.detect("rec:1")
    assert body(recorder) == {}


def test_editor_export(wave, recorder):
    wave.editor.export("prj_1", format="mp4", quality="high")
    assert sent(recorder) == ("POST", "/v1/editor/projects/prj_1/export")
    assert body(recorder) == {"format": "mp4", "quality": "high"}


def test_collab_delete_room_and_deprecated_alias(wave, recorder):
    recorder.set(lambda _r: httpx.Response(204))
    wave.collab.delete_room("room_1")
    assert sent(recorder) == ("DELETE", "/v1/collab/rooms/room_1")
    with pytest.warns(DeprecationWarning):
        wave.collab.close_room("room_2")
    assert sent(recorder) == ("DELETE", "/v1/collab/rooms/room_2")


def test_podcast_uses_the_published_show_paths(wave, recorder):
    wave.podcast.list(page=2)
    assert sent(recorder) == ("GET", "/v1/podcast/shows?page=2")
    recorder.set(lambda _r: httpx.Response(201, json={"id": "show_1", "name": "My Show"}))
    show = wave.podcast.create("My Show", category="tech")
    assert sent(recorder) == ("POST", "/v1/podcast/shows")
    assert body(recorder) == {"name": "My Show", "category": "tech"}
    assert show.id == "show_1"
    wave.podcast.list_episodes("show_1")
    assert sent(recorder) == ("GET", "/v1/podcast/shows/show_1/episodes")
    recorder.set(lambda _r: httpx.Response(201, json={"id": "ep_1"}))
    wave.podcast.create_episode("show_1", "Ep 1", audio_url="https://example.com/a.mp3")
    assert sent(recorder) == ("POST", "/v1/podcast/shows/show_1/episodes")
    assert body(recorder) == {"title": "Ep 1", "audioUrl": "https://example.com/a.mp3"}


@pytest.mark.parametrize(
    "call",
    [
        lambda w: w.clips.detect_highlights("stream", "s1"),
        lambda w: w.voice.synthesize("t", "v"),
        lambda w: w.captions.get_text("c1"),
        lambda w: w.chapters.get_default_set("a1"),
        lambda w: w.chapters.add_chapter("s1", "t", 0, 1),
        lambda w: w.editor.render("p1"),
        lambda w: w.podcast.get("show_1"),
        lambda w: w.podcast.update("show_1", name="n"),
        lambda w: w.podcast.remove("show_1"),
        lambda w: w.podcast.get_episode("ep_1"),
        lambda w: w.podcast.publish_episode("ep_1"),
        lambda w: w.podcast.get_rss_feed("show_1"),
        lambda w: w.podcast.get_analytics("show_1"),
        lambda w: w.podcast.distribute("show_1", ["spotify"]),
    ],
)
def test_methods_on_unpublished_paths_warn(wave, recorder, call):
    from wave_sdk import RouteNotServedError

    recorder.set(lambda _r: live_response("err_route_not_found_404"))
    with pytest.warns(DeprecationWarning), pytest.raises(RouteNotServedError):
        call(wave)


@pytest.mark.parametrize(
    "call",
    [
        lambda w: w.inference.complete("m", [{"role": "user", "content": "hi"}]),
        lambda w: w.realtime.publish("stream:abc", "note", {"x": 1}),
        lambda w: w.voice.generate("hello", "voice_1"),
        lambda w: w.clips.detect("video_1"),
        lambda w: w.chapters.detect("video_1"),
        lambda w: w.chapters.create_chapter("video_1", "Intro", 0, 1),
        lambda w: w.editor.export("prj_1"),
        lambda w: w.podcast.create("Show"),
        lambda w: w.podcast.create_episode("show_1", "Ep", audio_url="https://example.com/a.mp3"),
    ],
)
def test_billed_or_broadcast_writes_are_sent_once(wave, recorder, call):
    """A bare 5xx after the server may have accepted the request is raised, not retried: a retry
    could bill a job twice or broadcast an event twice. (The fixture fails on any retry sleep.)"""
    from wave_sdk import WaveError

    recorder.set(lambda _r: httpx.Response(502, text="bad gateway"))
    with pytest.raises(WaveError) as exc:
        call(wave)
    assert exc.value.status_code == 502
    assert len(recorder.requests) == 1


def test_ids_stay_one_path_segment(wave, recorder):
    """An id carrying '/', '?' or '#' must not move the request to another route."""
    recorder.set(lambda _r: httpx.Response(204))
    wave.captions.download("job/1?x#y", language="en")
    assert sent(recorder) == ("GET", "/v1/captions/job%2F1%3Fx%23y/download?language=en")
    wave.editor.export("prj/1")
    assert sent(recorder) == ("POST", "/v1/editor/projects/prj%2F1/export")
    wave.collab.delete_room("room/1")
    assert sent(recorder) == ("DELETE", "/v1/collab/rooms/room%2F1")
    wave.podcast.list_episodes("show/1")
    assert sent(recorder) == ("GET", "/v1/podcast/shows/show%2F1/episodes")


_ID_CALLS = [
    lambda w, i: w.chapters.list_chapters(i),
    lambda w, i: w.editor.export(i),
    lambda w, i: w.collab.delete_room(i),
    lambda w, i: w.realtime.presence(i),
    lambda w, i: w.podcast.list_episodes(i),
]


@pytest.mark.parametrize("bad_id", ["..", ".", ""])
@pytest.mark.parametrize("call", _ID_CALLS)
def test_ids_that_are_dot_segments_are_refused(wave, recorder, call, bad_id):
    """``/v1/videos/../chapters`` resolves to ``/v1/chapters``: a dot-segment id would send the
    caller's key to a different route, so it is refused before anything is sent."""
    with pytest.raises(ValueError):
        call(wave, bad_id)
    assert recorder.requests == []


@pytest.mark.parametrize("call", _ID_CALLS)
def test_percent_encoded_dots_stay_one_opaque_segment(wave, recorder, call):
    """``%`` is encoded, so ``%2E%2E`` is sent as ``%252E%252E``: literal text, not a parent."""
    recorder.set(lambda _r: httpx.Response(204))
    call(wave, "%2E%2E")
    assert "/%252E%252E" in recorder.last.url.raw_path.decode()


@pytest.mark.parametrize("path", ["/v1/clips/..", "/v1/clips/../usage", "/v1/clips/./x", "/v1/clips/%2e%2e?x=1"])
def test_any_request_path_with_a_dot_segment_is_refused(wave, recorder, path):
    """Methods that interpolate ids without ``path_segment`` are covered by the client-wide check."""
    with pytest.raises(ValueError, match="dot segment"):
        wave.client.get(path)
    assert recorder.requests == []


def test_an_unencoded_dot_segment_id_is_refused_by_the_client(wave, recorder):
    with pytest.raises(ValueError, match="dot segment"):
        wave.clips.get("..")
    assert recorder.requests == []


def test_live_fixture_file_has_no_unscrubbed_ids():
    import re
    from pathlib import Path

    text = (Path(__file__).parent / "fixtures" / "live_responses.json").read_text()
    uuids = set(re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text))
    assert uuids <= {"00000000-0000-4000-8000-000000000000"}
    assert live("usage")["body"]["org"] == "org_fixture"
