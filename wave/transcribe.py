"""WAVE SDK - Transcribe API. Audio/video transcription with speaker diarization."""
from __future__ import annotations
import time
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class Speaker(BaseModel):
    id: str; label: str; segments_count: int = 0; total_duration: float = 0

class TranscriptionSegment(BaseModel):
    id: str; start_time: float; end_time: float; text: str; speaker_id: str | None = None; confidence: float = 1.0

class Transcription(BaseModel):
    id: str; asset_id: str | None = None; source_url: str | None = None; status: str; language: str; model: str = "default"; segments: list[TranscriptionSegment] | None = None; speakers: list[Speaker] | None = None; duration_seconds: float | None = None; created_at: str; updated_at: str

class TranscribeAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/transcribe"
    def create(self, source_url: str | None = None, asset_id: str | None = None, language: str = "en", model: str = "default", **kwargs: Any) -> Transcription: return Transcription(**self._client.post(self._base, json={"source_url": source_url, "asset_id": asset_id, "language": language, "model": model, **kwargs}))
    def get(self, transcription_id: str) -> Transcription: return Transcription(**self._client.get(f"{self._base}/{transcription_id}"))
    def list(self, **params: Any) -> dict: return self._client.get(self._base, params={k: v for k, v in params.items() if v is not None})
    def update(self, transcription_id: str, **kwargs: Any) -> Transcription: return Transcription(**self._client.patch(f"{self._base}/{transcription_id}", json=kwargs))
    def remove(self, transcription_id: str) -> None: self._client.delete(f"{self._base}/{transcription_id}")
    def get_segments(self, transcription_id: str) -> list[TranscriptionSegment]: return [TranscriptionSegment(**s) for s in self._client.get(f"{self._base}/{transcription_id}/segments")]
    def update_segment(self, transcription_id: str, segment_id: str, **kwargs: Any) -> TranscriptionSegment: return TranscriptionSegment(**self._client.patch(f"{self._base}/{transcription_id}/segments/{segment_id}", json=kwargs))
    def split_segment(self, transcription_id: str, segment_id: str, split_time: float) -> list[TranscriptionSegment]: return [TranscriptionSegment(**s) for s in self._client.post(f"{self._base}/{transcription_id}/segments/{segment_id}/split", json={"split_time": split_time})]
    def merge_segments(self, transcription_id: str, segment_ids: list[str]) -> TranscriptionSegment: return TranscriptionSegment(**self._client.post(f"{self._base}/{transcription_id}/segments/merge", json={"segment_ids": segment_ids}))
    def get_speakers(self, transcription_id: str) -> list[Speaker]: return [Speaker(**s) for s in self._client.get(f"{self._base}/{transcription_id}/speakers")]
    def update_speaker(self, transcription_id: str, speaker_id: str, **kwargs: Any) -> Speaker: return Speaker(**self._client.patch(f"{self._base}/{transcription_id}/speakers/{speaker_id}", json=kwargs))
    def merge_speakers(self, transcription_id: str, speaker_ids: list[str]) -> Speaker: return Speaker(**self._client.post(f"{self._base}/{transcription_id}/speakers/merge", json={"speaker_ids": speaker_ids}))
    def get_text(self, transcription_id: str, include_speakers: bool = False, include_timestamps: bool = False) -> dict: return self._client.get(f"{self._base}/{transcription_id}/text", params={"include_speakers": include_speakers, "include_timestamps": include_timestamps})
    def search(self, transcription_id: str, query: str) -> list[dict]: return self._client.get(f"{self._base}/{transcription_id}/search", params={"q": query})
    def export_transcription(self, transcription_id: str, format: str = "srt") -> dict: return self._client.get(f"{self._base}/{transcription_id}/export", params={"format": format})
    def detect_language(self, source_url: str) -> dict: return self._client.post(f"{self._base}/detect-language", json={"source_url": source_url})
    def estimate_cost(self, duration_seconds: float, model: str = "default") -> dict: return self._client.post(f"{self._base}/estimate", json={"duration_seconds": duration_seconds, "model": model})
    def get_supported_languages(self) -> list[dict]: return self._client.get(f"{self._base}/languages")
    def start_realtime(self, stream_id: str, language: str = "en", **kwargs: Any) -> dict: return self._client.post(f"{self._base}/realtime/start", json={"stream_id": stream_id, "language": language, **kwargs})
    def stop_realtime(self, stream_id: str) -> dict: return self._client.post(f"{self._base}/realtime/stop", json={"stream_id": stream_id})
    def get_realtime_status(self, stream_id: str) -> dict: return self._client.get(f"{self._base}/realtime/{stream_id}")
    def wait_for_ready(self, transcription_id: str, poll_interval: float = 2.0, timeout: float = 600.0) -> Transcription:
        start = time.time()
        while time.time() - start < timeout:
            t = self.get(transcription_id)
            if t.status == "ready": return t
            if t.status == "failed": raise RuntimeError("Transcription failed")
            time.sleep(poll_interval)
        raise TimeoutError(f"Transcription timed out after {timeout}s")
