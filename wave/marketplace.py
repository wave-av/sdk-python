"""WAVE SDK - Marketplace API. Templates, plugins, and asset marketplace."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class MarketplaceItem(BaseModel):
    id: str; name: str; description: str; type: str; status: str; author_name: str; version: str; price_cents: int = 0; downloads: int = 0; rating: float = 0; tags: list[str] | None = None; category: str; created_at: str; updated_at: str

class MarketplaceAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/marketplace"
    def list(self, **params: Any) -> dict: return self._client.get(self._base, params={k: v for k, v in params.items() if v is not None})
    def get(self, item_id: str) -> MarketplaceItem: return MarketplaceItem(**self._client.get(f"{self._base}/{item_id}"))
    def install(self, item_id: str) -> dict: return self._client.post(f"{self._base}/{item_id}/install")
    def uninstall(self, item_id: str) -> None: self._client.delete(f"{self._base}/{item_id}/install")
    def list_installed(self, **params: Any) -> dict: return self._client.get(f"{self._base}/installed", params={k: v for k, v in params.items() if v is not None})
    def publish(self, name: str, description: str, type: str, category: str, file_url: str, **kwargs: Any) -> MarketplaceItem: return MarketplaceItem(**self._client.post(self._base, json={"name": name, "description": description, "type": type, "category": category, "file_url": file_url, **kwargs}))
    def search(self, query: str, **params: Any) -> dict: return self._client.get(f"{self._base}/search", params={"q": query, **{k: v for k, v in params.items() if v is not None}})
    def add_review(self, item_id: str, rating: int, comment: str) -> dict: return self._client.post(f"{self._base}/{item_id}/reviews", json={"rating": rating, "comment": comment})
