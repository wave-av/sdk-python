"""WAVE SDK - Perception API. Agentic live-media perception: the uniform
`subscribe()` verb. ONE call attaches an agent to ANY live stream - a WHEP
playback URL, an `srt://` URI, or a Cloudflare Stream live-input uid - and
returns the normalized receive descriptor a WHEP/SRT receiver (the "agent as
receive-endpoint") uses to attach, decode, sample frames, and hand them to
gateway-native inference at `/v1/messages`.

ONE RAIL, METERED SERVER-SIDE: the gateway is the sole meter emitter.
`subscribe()` consumes nothing itself - it names the existing meters the
session will bill on: the transport's delivered-minutes meter for delivery,
and the per-tier `wave_ai_tokens_*` meters for inference. Auth, scope
(`perception:write`), entitlement, rate limit, and metering are all enforced
by the gateway; the SDK only forwards the API key.

The perception control plane is inert until the operator arms it
(`WAVE_PERCEPTION_ENABLED=1`); until then every route fail-closes 503
(`PERCEPTION_UNCONFIGURED`).
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from wave_sdk.client import WaveClient

PerceptionTransport = Literal["whep", "srt"]
PerceptionSampleMode = Literal["adaptive", "fixed", "keyframe"]
PerceptionAudioMode = Literal["transcribe", "raw", "off"]


class PerceptionSample(BaseModel):
    mode: PerceptionSampleMode | None = None
    max_fps: float | None = None
    min_interval_ms: int | None = None


class PerceptionFrame(BaseModel):
    encoding: Literal["jpeg"] | None = None
    max_edge: int | None = None


class PerceptionBatch(BaseModel):
    max_frames: int | None = None
    max_delay_ms: int | None = None


class ReceiveDescriptor(BaseModel):
    whep_url: str | None
    srt_url: str | None


class PerceptionMeterBinding(BaseModel):
    delivery: str
    ai_tokens_in: str
    ai_tokens_out: str


class PerceptionAudioEcho(BaseModel):
    mode: PerceptionAudioMode


class PerceptionOptionsEcho(BaseModel):
    sample: PerceptionSample
    audio: PerceptionAudioEcho
    frame: PerceptionFrame
    batch: PerceptionBatch
    model: str


class PerceptionSubscription(BaseModel):
    ok: Literal[True]
    subscription_id: str
    org: str
    transport: PerceptionTransport
    receive: ReceiveDescriptor
    task: str | None
    inference_endpoint: str
    meters: PerceptionMeterBinding
    sample: PerceptionSample
    audio: PerceptionAudioEcho
    frame: PerceptionFrame
    batch: PerceptionBatch
    model: str


class PerceptionAPI:
    """Agentic live-media perception - subscribe an agent to any live stream and
    let it perceive + reason over the frames, metered on one rail by the gateway."""

    def __init__(self, client: WaveClient):
        self._client = client
        self._base = "/v1/perception"

    def subscribe(
        self,
        stream: str,
        task: str | None = None,
        sample: PerceptionSample | dict[str, Any] | None = None,
        audio: PerceptionAudioMode | None = None,
        frame: PerceptionFrame | dict[str, Any] | None = None,
        batch: PerceptionBatch | dict[str, Any] | None = None,
        model: str | None = None,
    ) -> PerceptionSubscription:
        """Open a perception session over any transport. Returns the receive
        descriptor + subscription id + meter binding."""
        body: dict[str, Any] = {"stream": stream}
        if task is not None:
            body["task"] = task
        if sample is not None:
            body["sample"] = sample.model_dump(exclude_none=True) if isinstance(sample, PerceptionSample) else sample
        if audio is not None:
            body["audio"] = audio
        if frame is not None:
            body["frame"] = frame.model_dump(exclude_none=True) if isinstance(frame, PerceptionFrame) else frame
        if batch is not None:
            body["batch"] = batch.model_dump(exclude_none=True) if isinstance(batch, PerceptionBatch) else batch
        if model is not None:
            body["model"] = model
        return PerceptionSubscription(**self._client.post(f"{self._base}/subscribe", json=body))

    def unsubscribe(self, subscription_id: str) -> None:
        """Close a subscription (idempotent control-plane close ack). `subscription_id`
        is the `psub_...` id from `subscribe`."""
        self._client.delete(f"{self._base}/subscribe/{subscription_id}")

    @staticmethod
    def receive_url(sub: PerceptionSubscription) -> str | None:
        """The single populated receive URL for a subscription, regardless of
        transport (convenience for receivers)."""
        return sub.receive.whep_url or sub.receive.srt_url
