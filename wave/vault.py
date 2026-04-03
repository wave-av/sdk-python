"""WAVE SDK - Vault API. Recording storage, VOD management, and archival."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class Recording(BaseModel):
    id: str; organization_id: str; stream_id: str | None = None; title: str; status: str; duration_seconds: float = 0; file_size_bytes: int = 0; format: str | None = None; storage_tier: str = "hot"; playback_url: str | None = None; download_url: str | None = None; tags: list[str] | None = None; created_at: str; updated_at: str

class VaultAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/vault"
    def list(self, **params: Any) -> dict: return self._client.get(f"{self._base}/recordings", params={k: v for k, v in params.items() if v is not None})
    def get(self, recording_id: str) -> Recording: return Recording(**self._client.get(f"{self._base}/recordings/{recording_id}"))
    def update(self, recording_id: str, **kwargs: Any) -> Recording: return Recording(**self._client.patch(f"{self._base}/recordings/{recording_id}", json=kwargs))
    def remove(self, recording_id: str) -> None: self._client.delete(f"{self._base}/recordings/{recording_id}")
    def get_storage_usage(self) -> dict: return self._client.get(f"{self._base}/storage")
    def create_upload(self, title: str, format: str, file_size_bytes: int, **kwargs: Any) -> dict: return self._client.post(f"{self._base}/uploads", json={"title": title, "format": format, "file_size_bytes": file_size_bytes, **kwargs})
    def complete_upload(self, upload_id: str) -> Recording: return Recording(**self._client.post(f"{self._base}/uploads/{upload_id}/complete"))
    def start_recording(self, stream_id: str, **kwargs: Any) -> Recording: return Recording(**self._client.post(f"{self._base}/recordings", json={"stream_id": stream_id, **kwargs}))
    def stop_recording(self, stream_id: str) -> Recording: return Recording(**self._client.post(f"{self._base}/recordings/stop", json={"stream_id": stream_id}))
    def transcode(self, recording_id: str, format: str, **kwargs: Any) -> dict: return self._client.post(f"{self._base}/recordings/{recording_id}/transcode", json={"format": format, **kwargs})
    def get_download_url(self, recording_id: str) -> dict: return self._client.get(f"{self._base}/recordings/{recording_id}/download")
