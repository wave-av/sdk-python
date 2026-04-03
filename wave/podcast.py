"""WAVE SDK - Podcast API. Podcast production, episodes, and distribution."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class Podcast(BaseModel):
    id: str; organization_id: str; title: str; description: str; category: str; language: str = "en"; episode_count: int = 0; subscriber_count: int = 0; rss_url: str | None = None; created_at: str; updated_at: str

class Episode(BaseModel):
    id: str; podcast_id: str; title: str; description: str; status: str; audio_url: str | None = None; duration_seconds: float = 0; published_at: str | None = None; created_at: str; updated_at: str

class PodcastAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/podcasts"
    def create(self, title: str, description: str, category: str, **kwargs: Any) -> Podcast: return Podcast(**self._client.post(self._base, json={"title": title, "description": description, "category": category, **kwargs}))
    def get(self, podcast_id: str) -> Podcast: return Podcast(**self._client.get(f"{self._base}/{podcast_id}"))
    def update(self, podcast_id: str, **kwargs: Any) -> Podcast: return Podcast(**self._client.patch(f"{self._base}/{podcast_id}", json=kwargs))
    def remove(self, podcast_id: str) -> None: self._client.delete(f"{self._base}/{podcast_id}")
    def list(self, **params: Any) -> dict: return self._client.get(self._base, params={k: v for k, v in params.items() if v is not None})
    def create_episode(self, podcast_id: str, title: str, description: str, **kwargs: Any) -> Episode: return Episode(**self._client.post(f"{self._base}/{podcast_id}/episodes", json={"title": title, "description": description, **kwargs}))
    def get_episode(self, episode_id: str) -> Episode: return Episode(**self._client.get(f"/v1/episodes/{episode_id}"))
    def publish_episode(self, episode_id: str) -> Episode: return Episode(**self._client.post(f"/v1/episodes/{episode_id}/publish"))
    def list_episodes(self, podcast_id: str, **params: Any) -> dict: return self._client.get(f"{self._base}/{podcast_id}/episodes", params={k: v for k, v in params.items() if v is not None})
    def get_rss_feed(self, podcast_id: str) -> dict: return self._client.get(f"{self._base}/{podcast_id}/rss")
    def get_analytics(self, podcast_id: str, **params: Any) -> dict: return self._client.get(f"{self._base}/{podcast_id}/analytics", params={k: v for k, v in params.items() if v is not None})
    def distribute(self, podcast_id: str, targets: list[str]) -> list[dict]: return self._client.post(f"{self._base}/{podcast_id}/distribute", json={"targets": targets})
