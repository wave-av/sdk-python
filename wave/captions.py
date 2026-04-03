"""WAVE SDK - Captions API. Auto-generate, translate, burn-in, and manage captions."""
from __future__ import annotations
import time
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class CaptionTrack(BaseModel):
    id: str; asset_id: str; language: str; status: str; format: str; cue_count: int = 0; download_url: str | None = None; created_at: str; updated_at: str

class CaptionCue(BaseModel):
    id: str; start_time: float; end_time: float; text: str; speaker_id: str | None = None

class BurnInJob(BaseModel):
    id: str; caption_id: str; status: str; progress_percent: int = 0; output_url: str | None = None; error: str | None = None; created_at: str

class CaptionsAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/captions"
    def generate(self, media_id: str, media_type: str = "video", language: str = "en", **kwargs: Any) -> CaptionTrack: return CaptionTrack(**self._client.post(self._base, json={"media_id": media_id, "media_type": media_type, "language": language, **kwargs}))
    def get(self, caption_id: str) -> CaptionTrack: return CaptionTrack(**self._client.get(f"{self._base}/{caption_id}"))
    def list(self, **params: Any) -> dict: return self._client.get(self._base, params={k: v for k, v in params.items() if v is not None})
    def update(self, caption_id: str, **kwargs: Any) -> CaptionTrack: return CaptionTrack(**self._client.patch(f"{self._base}/{caption_id}", json=kwargs))
    def remove(self, caption_id: str) -> None: self._client.delete(f"{self._base}/{caption_id}")
    def upload(self, media_id: str, language: str, format: str, content: str, **kwargs: Any) -> CaptionTrack: return CaptionTrack(**self._client.post(f"{self._base}/upload", json={"media_id": media_id, "language": language, "format": format, "content": content, **kwargs}))
    def translate(self, caption_id: str, target_language: str) -> CaptionTrack: return CaptionTrack(**self._client.post(f"{self._base}/{caption_id}/translate", json={"target_language": target_language}))
    def get_cues(self, caption_id: str) -> list[CaptionCue]: return [CaptionCue(**c) for c in self._client.get(f"{self._base}/{caption_id}/cues")]
    def add_cue(self, caption_id: str, start_time: float, end_time: float, text: str, **kwargs: Any) -> CaptionCue: return CaptionCue(**self._client.post(f"{self._base}/{caption_id}/cues", json={"start_time": start_time, "end_time": end_time, "text": text, **kwargs}))
    def update_cue(self, caption_id: str, cue_id: str, **kwargs: Any) -> CaptionCue: return CaptionCue(**self._client.patch(f"{self._base}/{caption_id}/cues/{cue_id}", json=kwargs))
    def remove_cue(self, caption_id: str, cue_id: str) -> None: self._client.delete(f"{self._base}/{caption_id}/cues/{cue_id}")
    def bulk_update_cues(self, caption_id: str, cues: list[dict]) -> list[CaptionCue]: return [CaptionCue(**c) for c in self._client.put(f"{self._base}/{caption_id}/cues", json={"cues": cues})]
    def export_format(self, caption_id: str, format: str = "srt") -> dict: return self._client.get(f"{self._base}/{caption_id}/export", params={"format": format})
    def get_text(self, caption_id: str, include_speakers: bool = False) -> dict: return self._client.get(f"{self._base}/{caption_id}/text", params={"include_speakers": include_speakers})
    def detect_language(self, media_id: str) -> dict: return self._client.post(f"{self._base}/detect-language", json={"media_id": media_id})
    def get_supported_languages(self) -> list[dict]: return self._client.get(f"{self._base}/languages")
    def get_for_media(self, media_id: str, media_type: str = "video") -> list[CaptionTrack]: return [CaptionTrack(**t) for t in self._client.get(f"{self._base}/media/{media_id}", params={"media_type": media_type})]
    def burn_in(self, caption_id: str, **kwargs: Any) -> BurnInJob: return BurnInJob(**self._client.post(f"{self._base}/{caption_id}/burn-in", json=kwargs))
    def get_burn_in_job(self, job_id: str) -> BurnInJob: return BurnInJob(**self._client.get(f"{self._base}/burn-in/{job_id}"))
    def wait_for_ready(self, caption_id: str, poll_interval: float = 2.0, timeout: float = 300.0) -> CaptionTrack:
        start = time.time()
        while time.time() - start < timeout:
            t = self.get(caption_id)
            if t.status == "ready": return t
            if t.status == "failed": raise RuntimeError("Caption generation failed")
            time.sleep(poll_interval)
        raise TimeoutError(f"Caption timed out after {timeout}s")
    def wait_for_burn_in(self, job_id: str, poll_interval: float = 3.0, timeout: float = 600.0) -> BurnInJob:
        start = time.time()
        while time.time() - start < timeout:
            j = self.get_burn_in_job(job_id)
            if j.status == "ready": return j
            if j.status == "failed": raise RuntimeError(f"Burn-in failed: {j.error}")
            time.sleep(poll_interval)
        raise TimeoutError(f"Burn-in timed out after {timeout}s")
