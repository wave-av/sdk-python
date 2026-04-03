"""WAVE SDK - Autopilot API (formerly Ghost Producer). AI-powered autonomous production directing."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class GhostSession(BaseModel):
    id: str; production_id: str; mode: str; style: str; status: str; confidence_threshold: float = 0.7; created_at: str | None = None

class GhostAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/productions"
    def start(self, production_id: str, mode: str = "assisted", style: str = "conference", **kwargs: Any) -> GhostSession: return GhostSession(**self._client.post(f"{self._base}/{production_id}/ghost", json={"mode": mode, "style": style, **kwargs}))
    def get(self, production_id: str) -> GhostSession: return GhostSession(**self._client.get(f"{self._base}/{production_id}/ghost"))
    def update(self, production_id: str, **kwargs: Any) -> GhostSession: return GhostSession(**self._client.patch(f"{self._base}/{production_id}/ghost", json=kwargs))
    def stop(self, production_id: str) -> None: self._client.post(f"{self._base}/{production_id}/ghost/stop")
    def pause(self, production_id: str) -> None: self._client.post(f"{self._base}/{production_id}/ghost/pause")
    def resume(self, production_id: str) -> None: self._client.post(f"{self._base}/{production_id}/ghost/resume")
    def override(self, production_id: str, source_id: str, duration_ms: int = 5000) -> None: self._client.post(f"{self._base}/{production_id}/ghost/override", json={"source_id": source_id, "duration_ms": duration_ms})
    def list_suggestions(self, production_id: str, **params: Any) -> dict: return self._client.get(f"{self._base}/{production_id}/ghost/suggestions", params={k: v for k, v in params.items() if v is not None})
    def get_stats(self, production_id: str) -> dict: return self._client.get(f"{self._base}/{production_id}/ghost/stats")
