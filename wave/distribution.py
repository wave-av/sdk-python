"""WAVE SDK - Distribution API. Social simulcasting and scheduled publishing."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class Destination(BaseModel):
    id: str; organization_id: str; name: str; type: str; status: str; auto_start: bool = False; created_at: str; updated_at: str

class DistributionAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/distribution"
    def list_destinations(self, **params: Any) -> dict: return self._client.get(f"{self._base}/destinations", params={k: v for k, v in params.items() if v is not None})
    def get_destination(self, dest_id: str) -> Destination: return Destination(**self._client.get(f"{self._base}/destinations/{dest_id}"))
    def add_destination(self, name: str, type: str, **kwargs: Any) -> Destination: return Destination(**self._client.post(f"{self._base}/destinations", json={"name": name, "type": type, **kwargs}))
    def remove_destination(self, dest_id: str) -> None: self._client.delete(f"{self._base}/destinations/{dest_id}")
    def start_simulcast(self, stream_id: str, destination_ids: list[str]) -> dict: return self._client.post(f"{self._base}/simulcast", json={"stream_id": stream_id, "destination_ids": destination_ids})
    def stop_simulcast(self, stream_id: str) -> dict: return self._client.post(f"{self._base}/simulcast/stop", json={"stream_id": stream_id})
    def get_simulcast_status(self, stream_id: str) -> dict: return self._client.get(f"{self._base}/simulcast/{stream_id}")
    def schedule_post(self, title: str, platforms: list[str], media_url: str, scheduled_at: str, **kwargs: Any) -> dict: return self._client.post(f"{self._base}/posts", json={"title": title, "platforms": platforms, "media_url": media_url, "scheduled_at": scheduled_at, **kwargs})
    def list_scheduled_posts(self, **params: Any) -> dict: return self._client.get(f"{self._base}/posts", params={k: v for k, v in params.items() if v is not None})
    def cancel_scheduled_post(self, post_id: str) -> None: self._client.delete(f"{self._base}/posts/{post_id}")
