"""WAVE SDK - Search API. Full-text, visual, audio, and semantic search across content."""
from __future__ import annotations
import time
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class SearchResult(BaseModel):
    id: str; type: str; title: str; score: float; highlights: list[dict] | None = None; thumbnail_url: str | None = None; created_at: str

class SearchAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/search"
    def search(self, query: str, **kwargs: Any) -> dict: return self._client.post(self._base, json={"query": query, **kwargs})
    def quick_search(self, query: str, limit: int = 10) -> dict: return self._client.get(f"{self._base}/quick", params={"q": query, "limit": limit})
    def visual_search(self, image_url: str, **kwargs: Any) -> dict: return self._client.post(f"{self._base}/visual", json={"image_url": image_url, **kwargs})
    def audio_search(self, audio_url: str, **kwargs: Any) -> dict: return self._client.post(f"{self._base}/audio", json={"audio_url": audio_url, **kwargs})
    def search_in_media(self, media_id: str, media_type: str, query: str) -> dict: return self._client.post(f"{self._base}/media/{media_id}", json={"media_type": media_type, "query": query})
    def find_similar_frames(self, media_id: str, frame_time: float, **kwargs: Any) -> dict: return self._client.post(f"{self._base}/similar/frames", json={"media_id": media_id, "frame_time": frame_time, **kwargs})
    def find_similar_audio(self, media_id: str, start_time: float, end_time: float) -> dict: return self._client.post(f"{self._base}/similar/audio", json={"media_id": media_id, "start_time": start_time, "end_time": end_time})
    def detect_objects(self, media_id: str, **kwargs: Any) -> dict: return self._client.post(f"{self._base}/detect/objects", json={"media_id": media_id, **kwargs})
    def detect_music(self, media_id: str) -> dict: return self._client.post(f"{self._base}/detect/music", json={"media_id": media_id})
    def get_suggestions(self, query: str, limit: int = 5) -> list[str]: return self._client.get(f"{self._base}/suggest", params={"q": query, "limit": limit})
    def get_trending(self, **params: Any) -> dict: return self._client.get(f"{self._base}/trending", params={k: v for k, v in params.items() if v is not None})
    def get_analytics(self, **params: Any) -> dict: return self._client.get(f"{self._base}/analytics", params={k: v for k, v in params.items() if v is not None})
    def index_media(self, media_id: str, media_type: str = "video") -> dict: return self._client.post(f"{self._base}/index", json={"media_id": media_id, "media_type": media_type})
    def reindex_media(self, media_id: str) -> dict: return self._client.post(f"{self._base}/index/reindex", json={"media_id": media_id})
    def remove_from_index(self, media_id: str) -> None: self._client.delete(f"{self._base}/index/{media_id}")
    def get_index_status(self) -> dict: return self._client.get(f"{self._base}/index/status")
    def save_search(self, name: str, query: str, filters: dict | None = None) -> dict: return self._client.post(f"{self._base}/saved", json={"name": name, "query": query, "filters": filters})
    def list_saved_searches(self) -> list[dict]: return self._client.get(f"{self._base}/saved")
    def run_saved_search(self, saved_id: str) -> dict: return self._client.post(f"{self._base}/saved/{saved_id}/run")
    def remove_saved_search(self, saved_id: str) -> None: self._client.delete(f"{self._base}/saved/{saved_id}")
    def wait_for_index(self, media_id: str, poll_interval: float = 3.0, timeout: float = 300.0) -> dict:
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_index_status()
            if status.get("indexed"): return status
            time.sleep(poll_interval)
        raise TimeoutError(f"Indexing timed out after {timeout}s")
