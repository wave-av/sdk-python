"""WAVE SDK - Pipeline API. Live stream management across protocols."""
from __future__ import annotations
import time
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class Stream(BaseModel):
    id: str; organization_id: str; title: str; description: str | None = None; status: str; protocol: str; ingest_url: str | None = None; playback_url: str | None = None; stream_key: str | None = None; resolution: str | None = None; frame_rate: int | None = None; bitrate_kbps: int | None = None; viewer_count: int = 0; recording_enabled: bool = False; tags: list[str] | None = None; metadata: dict[str, Any] | None = None; started_at: str | None = None; ended_at: str | None = None; created_at: str; updated_at: str

class StreamHealth(BaseModel):
    stream_id: str; status: str; bitrate_kbps: int; frame_rate: float; dropped_frames: int; latency_ms: int; viewer_count: int; uptime_seconds: int

class StreamRecording(BaseModel):
    id: str; stream_id: str; status: str; duration: float | None = None; file_size: int | None = None; download_url: str | None = None; playback_url: str | None = None; created_at: str

class PipelineAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/streams"
    def create(self, title: str, protocol: str = "webrtc", **kwargs: Any) -> Stream: return Stream(**self._client.post(self._base, json={"title": title, "protocol": protocol, **kwargs}))
    def get(self, stream_id: str) -> Stream: return Stream(**self._client.get(f"{self._base}/{stream_id}"))
    def update(self, stream_id: str, **kwargs: Any) -> Stream: return Stream(**self._client.patch(f"{self._base}/{stream_id}", json=kwargs))
    def remove(self, stream_id: str) -> None: self._client.delete(f"{self._base}/{stream_id}")
    def list(self, **params: Any) -> dict: return self._client.get(self._base, params={k: v for k, v in params.items() if v is not None})
    def start(self, stream_id: str) -> Stream: return Stream(**self._client.post(f"{self._base}/{stream_id}/start"))
    def stop(self, stream_id: str) -> Stream: return Stream(**self._client.post(f"{self._base}/{stream_id}/stop"))
    def get_health(self, stream_id: str) -> StreamHealth: return StreamHealth(**self._client.get(f"{self._base}/{stream_id}/health"))
    def get_ingest_endpoints(self, stream_id: str) -> list[dict]: return self._client.get(f"{self._base}/{stream_id}/ingest")
    def start_recording(self, stream_id: str) -> StreamRecording: return StreamRecording(**self._client.post(f"{self._base}/{stream_id}/recording/start"))
    def stop_recording(self, stream_id: str) -> StreamRecording: return StreamRecording(**self._client.post(f"{self._base}/{stream_id}/recording/stop"))
    def list_recordings(self, stream_id: str, **params: Any) -> dict: return self._client.get(f"{self._base}/{stream_id}/recordings", params={k: v for k, v in params.items() if v is not None})
    def get_viewer_count(self, stream_id: str) -> dict: return self._client.get(f"{self._base}/{stream_id}/viewers/count")
    def switch_protocol(self, stream_id: str, protocol: str) -> Stream: return Stream(**self._client.post(f"{self._base}/{stream_id}/protocol", json={"protocol": protocol}))
    def wait_for_live(self, stream_id: str, poll_interval: float = 2.0, timeout: float = 120.0) -> Stream:
        start = time.time()
        while time.time() - start < timeout:
            s = self.get(stream_id)
            if s.status == "live": return s
            if s.status == "failed": raise RuntimeError("Stream failed to go live")
            time.sleep(poll_interval)
        raise TimeoutError(f"Stream did not go live within {timeout}s")
