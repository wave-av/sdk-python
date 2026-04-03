"""WAVE SDK - Signage API. Digital signage display and playlist management."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class Display(BaseModel):
    id: str; organization_id: str; name: str; status: str; resolution: str | None = None; orientation: str = "landscape"; location: str | None = None; current_playlist_id: str | None = None; last_seen_at: str | None = None; created_at: str; updated_at: str

class SignageAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/signage"
    def list_displays(self, **params: Any) -> dict: return self._client.get(f"{self._base}/displays", params={k: v for k, v in params.items() if v is not None})
    def get_display(self, display_id: str) -> Display: return Display(**self._client.get(f"{self._base}/displays/{display_id}"))
    def register_display(self, name: str, **kwargs: Any) -> Display: return Display(**self._client.post(f"{self._base}/displays", json={"name": name, **kwargs}))
    def remove_display(self, display_id: str) -> None: self._client.delete(f"{self._base}/displays/{display_id}")
    def create_playlist(self, name: str, items: list[dict], **kwargs: Any) -> dict: return self._client.post(f"{self._base}/playlists", json={"name": name, "items": items, **kwargs})
    def list_playlists(self, **params: Any) -> dict: return self._client.get(f"{self._base}/playlists", params={k: v for k, v in params.items() if v is not None})
    def assign_playlist(self, display_id: str, playlist_id: str) -> None: self._client.post(f"{self._base}/displays/{display_id}/playlist", json={"playlist_id": playlist_id})
    def schedule_content(self, playlist_id: str, display_ids: list[str], start_time: str, end_time: str, **kwargs: Any) -> dict: return self._client.post(f"{self._base}/schedules", json={"playlist_id": playlist_id, "display_ids": display_ids, "start_time": start_time, "end_time": end_time, **kwargs})
    def configure_display(self, display_id: str, **config: Any) -> dict: return self._client.patch(f"{self._base}/displays/{display_id}/config", json=config)
