"""WAVE SDK - Voice API. Text-to-speech synthesis and voice cloning."""
from __future__ import annotations
import time
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class Voice(BaseModel):
    id: str; name: str; language: str; gender: str | None = None; model_type: str; preview_url: str | None = None; is_custom: bool = False; created_at: str; updated_at: str

class SynthesisResult(BaseModel):
    id: str; voice_id: str; status: str; audio_url: str | None = None; duration_seconds: float | None = None; format: str; error: str | None = None; created_at: str

class VoiceCloneJob(BaseModel):
    id: str; name: str; status: str; voice_id: str | None = None; error: str | None = None; created_at: str

class VoiceAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/voice"
    def list_voices(self, **params: Any) -> dict: return self._client.get(f"{self._base}/voices", params={k: v for k, v in params.items() if v is not None})
    def get_voice(self, voice_id: str) -> Voice: return Voice(**self._client.get(f"{self._base}/voices/{voice_id}"))
    def remove_voice(self, voice_id: str) -> None: self._client.delete(f"{self._base}/voices/{voice_id}")
    def get_voice_settings(self, voice_id: str) -> dict: return self._client.get(f"{self._base}/voices/{voice_id}/settings")
    def update_voice_settings(self, voice_id: str, **kwargs: Any) -> dict: return self._client.patch(f"{self._base}/voices/{voice_id}/settings", json=kwargs)
    def get_supported_languages(self) -> list[dict]: return self._client.get(f"{self._base}/languages")
    def synthesize(self, text: str, voice_id: str, format: str = "mp3", **kwargs: Any) -> SynthesisResult: return SynthesisResult(**self._client.post(f"{self._base}/synthesize", json={"text": text, "voice_id": voice_id, "format": format, **kwargs}))
    def synthesize_stream(self, text: str, voice_id: str) -> dict: return self._client.post(f"{self._base}/synthesize/stream", json={"text": text, "voice_id": voice_id})
    def get_synthesis(self, synthesis_id: str) -> SynthesisResult: return SynthesisResult(**self._client.get(f"{self._base}/syntheses/{synthesis_id}"))
    def list_syntheses(self, **params: Any) -> dict: return self._client.get(f"{self._base}/syntheses", params={k: v for k, v in params.items() if v is not None})
    def estimate_cost(self, text: str, voice_id: str) -> dict: return self._client.post(f"{self._base}/estimate", json={"text": text, "voice_id": voice_id})
    def clone_voice(self, name: str, sample_urls: list[str], **kwargs: Any) -> VoiceCloneJob: return VoiceCloneJob(**self._client.post(f"{self._base}/clone", json={"name": name, "sample_urls": sample_urls, **kwargs}))
    def get_clone_job(self, job_id: str) -> VoiceCloneJob: return VoiceCloneJob(**self._client.get(f"{self._base}/clone/{job_id}"))
    def list_clone_jobs(self, **params: Any) -> dict: return self._client.get(f"{self._base}/clone", params={k: v for k, v in params.items() if v is not None})
    def cancel_clone_job(self, job_id: str) -> None: self._client.post(f"{self._base}/clone/{job_id}/cancel")
    def wait_for_synthesis(self, synthesis_id: str, poll_interval: float = 1.0, timeout: float = 120.0) -> SynthesisResult:
        start = time.time()
        while time.time() - start < timeout:
            s = self.get_synthesis(synthesis_id)
            if s.status == "ready": return s
            if s.status == "failed": raise RuntimeError(f"Synthesis failed: {s.error}")
            time.sleep(poll_interval)
        raise TimeoutError(f"Synthesis timed out after {timeout}s")
    def wait_for_clone(self, job_id: str, poll_interval: float = 5.0, timeout: float = 600.0) -> VoiceCloneJob:
        start = time.time()
        while time.time() - start < timeout:
            j = self.get_clone_job(job_id)
            if j.status == "ready": return j
            if j.status == "failed": raise RuntimeError(f"Clone failed: {j.error}")
            time.sleep(poll_interval)
        raise TimeoutError(f"Clone timed out after {timeout}s")
