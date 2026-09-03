"""Unit tests for the 2.1.0 TS-namespace-parity additions: TranscriptAPI,
MailAPI, MeterAPI, PricingAPI, PerceptionAPI, InferenceAPI. HTTP is mocked at
the WaveClient method boundary (get/post/patch/delete) — no real network I/O.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from wave_sdk.inference import InferenceAPI
from wave_sdk.mail import MailAPI
from wave_sdk.meter import MeterAPI
from wave_sdk.perception import PerceptionAPI
from wave_sdk.pricing import ManifestCreateResult, PricingAPI, PricingManifest, PricingTier
from wave_sdk.transcripts import TranscriptAPI


@pytest.fixture
def mock_client():
    return MagicMock()


# ---------------------------------------------------------------------------
# TranscriptAPI
# ---------------------------------------------------------------------------

def test_transcripts_list(mock_client):
    mock_client.get.return_value = {"org": "acme", "count": 2, "transcripts": ["a", "b"]}
    api = TranscriptAPI(mock_client)
    result = api.list("acme")
    mock_client.get.assert_called_once_with("/v1/realtime/agents/transcripts/acme")
    assert result.org == "acme"
    assert result.count == 2
    assert result.transcripts == ["a", "b"]


def test_transcripts_get(mock_client):
    mock_client.get.return_value = {
        "org": "acme", "room_id": "room1", "session_id": "sess1", "recorded_at": 1730000000,
        "messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
    }
    api = TranscriptAPI(mock_client)
    result = api.get("acme", "room1", "sess1")
    mock_client.get.assert_called_once_with("/v1/realtime/agents/transcripts/acme/room1/sess1")
    assert result.room_id == "room1"
    assert len(result.messages) == 2
    assert result.messages[0].role == "user"


# ---------------------------------------------------------------------------
# MailAPI
# ---------------------------------------------------------------------------

def test_mail_send(mock_client):
    mock_client.post.return_value = {"message_id": "msg_1", "status": "queued"}
    api = MailAPI(mock_client)
    result = api.send(to="alice@example.com", subject="hi", text="body")
    mock_client.post.assert_called_once_with(
        "/v1/mail/send", json={"to": "alice@example.com", "subject": "hi", "text": "body"}
    )
    assert result.status == "queued"
    assert result.message_id == "msg_1"


def test_mail_reply(mock_client):
    mock_client.post.return_value = {"status": "sent"}
    api = MailAPI(mock_client)
    result = api.reply("msg_1", text="a reply")
    mock_client.post.assert_called_once_with("/v1/mail/reply/msg_1", json={"text": "a reply"})
    assert result.status == "sent"


def test_mail_search(mock_client):
    mock_client.get.return_value = {"threads": [{"id": "t1"}]}
    api = MailAPI(mock_client)
    result = api.search("invoice")
    mock_client.get.assert_called_once_with("/v1/mail/search", params={"q": "invoice"})
    assert result.threads == [{"id": "t1"}]


def test_mail_transcript_email(mock_client):
    mock_client.post.return_value = {"status": "queued"}
    api = MailAPI(mock_client)
    api.transcript_email(to="bob@example.com", transcript="hello world")
    mock_client.post.assert_called_once_with(
        "/v1/transcripts/email", json={"to": "bob@example.com", "transcript": "hello world"}
    )


def test_mail_sms(mock_client):
    mock_client.post.return_value = {"sid": "SM123", "status": "queued"}
    api = MailAPI(mock_client)
    result = api.sms(to="+15551234567", body="hello")
    mock_client.post.assert_called_once_with("/v1/sms/send", json={"to": "+15551234567", "body": "hello"})
    assert result.sid == "SM123"


# ---------------------------------------------------------------------------
# MeterAPI
# ---------------------------------------------------------------------------

def _channels():
    return {
        "mail": {"ops": 10, "usdc": "0.05", "errors": 0},
        "voice": {"minutes": 3.5, "usdc": "0.10"},
        "sms": {"ops": 2, "blocked": 0},
        "realtime": {"minutes": 12.0},
        "storage": {"bytes": 1024},
    }


def test_meter_ledger(mock_client):
    mock_client.get.return_value = {
        "rows": [{"org": "acme", "from": "2026-08-01", "to": "2026-08-31", "channels": _channels()}],
        "generated_at": "2026-09-01T00:00:00Z",
    }
    api = MeterAPI(mock_client)
    result = api.ledger(channel="mail")
    mock_client.get.assert_called_once_with("/v1/meter/ledger", params={"channel": "mail"})
    assert len(result.rows) == 1
    assert result.rows[0].from_ == "2026-08-01"
    assert result.rows[0].channels.mail.ops == 10


def test_meter_rollup(mock_client):
    mock_client.get.return_value = {
        "org": "acme", "from": "2026-08-01", "to": "2026-08-31",
        "totals": _channels(), "generated_at": "2026-09-01T00:00:00Z",
    }
    api = MeterAPI(mock_client)
    result = api.rollup(period="month")
    mock_client.get.assert_called_once_with("/v1/meter/ledger/rollup", params={"period": "month"})
    assert result.totals.voice.minutes == 3.5


# ---------------------------------------------------------------------------
# PricingAPI
# ---------------------------------------------------------------------------

def test_pricing_create_manifest(mock_client):
    mock_client.post.return_value = {"slug": "acme-news", "org": "acme", "status": "published", "updated_at": "2026-09-01T00:00:00Z"}
    api = PricingAPI(mock_client)
    manifest = PricingManifest(
        slug="acme-news", title="Acme News",
        tiers=[PricingTier(id="L1", name="Per article", price_usdc_micro="400", rail="x402", billing="per_op", features=["delivered"])],
    )
    result = api.create_manifest(manifest)
    assert mock_client.post.call_count == 1
    assert isinstance(result, ManifestCreateResult)
    assert result.slug == "acme-news"
    assert result.status == "published"


def test_pricing_list_manifests(mock_client):
    mock_client.get.return_value = {"org": "acme", "manifests": [{"slug": "acme-news", "title": "Acme News", "status": "published", "updated_at": "2026-09-01T00:00:00Z"}]}
    api = PricingAPI(mock_client)
    result = api.list_manifests()
    mock_client.get.assert_called_once_with("/v1/pricing/manifests")
    assert result.manifests[0].slug == "acme-news"


def test_pricing_get_manifest(mock_client):
    mock_client.get.return_value = {
        "org": "acme", "slug": "acme-news", "status": "published", "updated_at": "2026-09-01T00:00:00Z",
        "manifest": {"slug": "acme-news", "title": "Acme News", "tiers": []},
    }
    api = PricingAPI(mock_client)
    result = api.get_manifest("acme-news")
    mock_client.get.assert_called_once_with("/v1/pricing/manifests/acme-news")
    assert result.manifest.title == "Acme News"


# ---------------------------------------------------------------------------
# PerceptionAPI
# ---------------------------------------------------------------------------

def _subscription_payload():
    return {
        "ok": True, "subscription_id": "psub_1", "org": "acme", "transport": "srt",
        "receive": {"whep_url": None, "srt_url": "srt://ingest.example.com:9000"},
        "task": "flag goals", "inference_endpoint": "https://gateway.wave.online/v1/messages",
        "meters": {"delivery": "wave_stream_delivered_minutes", "ai_tokens_in": "wave_ai_tokens_haiku_input", "ai_tokens_out": "wave_ai_tokens_haiku_output"},
        "sample": {"mode": "adaptive", "max_fps": 2, "min_interval_ms": 2000},
        "audio": {"mode": "transcribe"},
        "frame": {"encoding": "jpeg", "max_edge": 1280},
        "batch": {"max_frames": 4, "max_delay_ms": 250},
        "model": "claude-haiku",
    }


def test_perception_subscribe(mock_client):
    mock_client.post.return_value = _subscription_payload()
    api = PerceptionAPI(mock_client)
    sub = api.subscribe(stream="srt://ingest.example.com:9000?streamid=game", task="flag goals", model="claude-haiku")
    mock_client.post.assert_called_once()
    args, kwargs = mock_client.post.call_args
    assert args[0] == "/v1/perception/subscribe"
    assert kwargs["json"]["stream"] == "srt://ingest.example.com:9000?streamid=game"
    assert sub.subscription_id == "psub_1"
    assert PerceptionAPI.receive_url(sub) == "srt://ingest.example.com:9000"


def test_perception_unsubscribe(mock_client):
    api = PerceptionAPI(mock_client)
    api.unsubscribe("psub_1")
    mock_client.delete.assert_called_once_with("/v1/perception/subscribe/psub_1")


# ---------------------------------------------------------------------------
# InferenceAPI
# ---------------------------------------------------------------------------

def test_inference_complete(monkeypatch):
    class FakeClient:
        api_key = "test-key"

    def fake_post(url, headers=None, json=None, timeout=None):
        assert url == "https://inference.wave.online/v1/chat/completions"
        assert headers["authorization"] == "Bearer test-key"
        return httpx.Response(200, json={
            "model": "claude-haiku", "choices": [{"message": {"content": "hi there"}}],
            "usage": {"cost": 0.0001, "total_tokens": 12},
        })

    monkeypatch.setattr("wave_sdk.inference.httpx.post", fake_post)
    api = InferenceAPI(FakeClient())
    result = api.complete("claude-haiku", [{"role": "user", "content": "hi"}])
    assert result.model == "claude-haiku"
    assert result.content == "hi there"
    assert result.total_tokens == 12


def test_inference_complete_raises_on_error(monkeypatch):
    class FakeClient:
        api_key = "test-key"

    def fake_post(url, headers=None, json=None, timeout=None):
        return httpx.Response(500, text="funnel down")

    monkeypatch.setattr("wave_sdk.inference.httpx.post", fake_post)
    api = InferenceAPI(FakeClient())
    from wave_sdk.client import WaveError
    with pytest.raises(WaveError):
        api.complete("claude-haiku", [{"role": "user", "content": "hi"}])


def test_inference_models_requires_registry():
    class FakeClient:
        api_key = "test-key"

    api = InferenceAPI(FakeClient())
    from wave_sdk.client import WaveError
    with pytest.raises(WaveError, match="registry_url"):
        api.models()


def test_inference_models_with_registry(monkeypatch):
    class FakeClient:
        api_key = "test-key"

    def fake_get(url, headers=None, timeout=None):
        assert url.startswith("https://registry.example.com/rest/v1/models")
        return httpx.Response(200, json=[{"id": "m1", "rail": "openai", "cost_input_per_m": 1.0, "cost_output_per_m": 2.0}])

    monkeypatch.setattr("wave_sdk.inference.httpx.get", fake_get)
    api = InferenceAPI(FakeClient(), registry_url="https://registry.example.com", registry_key="k")
    models = api.models()
    assert models[0].id == "m1"
    assert models[0].input_per_m == 1.0
