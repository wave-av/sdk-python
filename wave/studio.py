"""WAVE SDK - Studio API. Multi-camera broadcast production."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class Production(BaseModel):
    id: str; organization_id: str; title: str; description: str | None = None; status: str; program_source_id: str | None = None; preview_source_id: str | None = None; active_scene_id: str | None = None; recording_enabled: bool = False; streaming_enabled: bool = False; viewer_count: int = 0; started_at: str | None = None; ended_at: str | None = None; created_at: str; updated_at: str

class Source(BaseModel):
    id: str; production_id: str; name: str; type: str; url: str | None = None; status: str; tally: str; audio_level: float | None = None; volume: float = 1.0; muted: bool = False; ptz_enabled: bool = False

class Scene(BaseModel):
    id: str; production_id: str; name: str; layout: str; sources: list[dict[str, Any]] | None = None; is_active: bool = False; sort_order: int = 0

class Graphic(BaseModel):
    id: str; production_id: str; name: str; type: str; content: dict[str, Any] | None = None; position: dict[str, Any] | None = None; visible: bool = False; layer: int = 0

class StudioAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/productions"
    def create(self, title: str, **kwargs: Any) -> Production: return Production(**self._client.post(self._base, json={"title": title, **kwargs}))
    def get(self, production_id: str) -> Production: return Production(**self._client.get(f"{self._base}/{production_id}"))
    def update(self, production_id: str, **kwargs: Any) -> Production: return Production(**self._client.patch(f"{self._base}/{production_id}", json=kwargs))
    def remove(self, production_id: str) -> None: self._client.delete(f"{self._base}/{production_id}")
    def list(self, **params: Any) -> dict: return self._client.get(self._base, params={k: v for k, v in params.items() if v is not None})
    def start(self, production_id: str) -> Production: return Production(**self._client.post(f"{self._base}/{production_id}/start"))
    def stop(self, production_id: str) -> Production: return Production(**self._client.post(f"{self._base}/{production_id}/stop"))
    def start_rehearsal(self, production_id: str) -> Production: return Production(**self._client.post(f"{self._base}/{production_id}/rehearsal"))
    def add_source(self, production_id: str, name: str, type: str, url: str | None = None, **kwargs: Any) -> Source: return Source(**self._client.post(f"{self._base}/{production_id}/sources", json={"name": name, "type": type, "url": url, **kwargs}))
    def remove_source(self, production_id: str, source_id: str) -> None: self._client.delete(f"{self._base}/{production_id}/sources/{source_id}")
    def list_sources(self, production_id: str) -> list[Source]: return [Source(**s) for s in self._client.get(f"{self._base}/{production_id}/sources")]
    def create_scene(self, production_id: str, name: str, layout: str = "fullscreen", **kwargs: Any) -> Scene: return Scene(**self._client.post(f"{self._base}/{production_id}/scenes", json={"name": name, "layout": layout, **kwargs}))
    def activate_scene(self, production_id: str, scene_id: str, **kwargs: Any) -> Scene: return Scene(**self._client.post(f"{self._base}/{production_id}/scenes/{scene_id}/activate", json=kwargs if kwargs else None))
    def list_scenes(self, production_id: str) -> list[Scene]: return [Scene(**s) for s in self._client.get(f"{self._base}/{production_id}/scenes")]
    def set_program(self, production_id: str, source_id: str, **kwargs: Any) -> None: self._client.post(f"{self._base}/{production_id}/program", json={"source_id": source_id, **kwargs})
    def set_preview(self, production_id: str, source_id: str) -> None: self._client.post(f"{self._base}/{production_id}/preview", json={"source_id": source_id})
    def transition(self, production_id: str, type: str = "cut", duration_ms: int = 0) -> None: self._client.post(f"{self._base}/{production_id}/transition", json={"type": type, "duration_ms": duration_ms})
    def add_graphic(self, production_id: str, name: str, type: str, **kwargs: Any) -> Graphic: return Graphic(**self._client.post(f"{self._base}/{production_id}/graphics", json={"name": name, "type": type, **kwargs}))
    def show_graphic(self, production_id: str, graphic_id: str) -> None: self._client.post(f"{self._base}/{production_id}/graphics/{graphic_id}/show")
    def hide_graphic(self, production_id: str, graphic_id: str) -> None: self._client.post(f"{self._base}/{production_id}/graphics/{graphic_id}/hide")
    def get_audio_mix(self, production_id: str) -> list[dict]: return self._client.get(f"{self._base}/{production_id}/audio")
    def set_audio_mix(self, production_id: str, channels: list[dict]) -> list[dict]: return self._client.put(f"{self._base}/{production_id}/audio", json={"channels": channels})
