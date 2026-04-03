"""WAVE SDK - Connect API. Third-party integration and webhook management."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class Integration(BaseModel):
    id: str; organization_id: str; name: str; type: str; provider: str; status: str; scopes: list[str] | None = None; last_sync_at: str | None = None; error_message: str | None = None; created_at: str; updated_at: str

class ConnectAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/integrations"
    def list(self, **params: Any) -> dict: return self._client.get(self._base, params={k: v for k, v in params.items() if v is not None})
    def get(self, integration_id: str) -> Integration: return Integration(**self._client.get(f"{self._base}/{integration_id}"))
    def enable(self, provider: str, type: str, **kwargs: Any) -> Integration: return Integration(**self._client.post(self._base, json={"provider": provider, "type": type, **kwargs}))
    def disable(self, integration_id: str) -> None: self._client.post(f"{self._base}/{integration_id}/disable")
    def configure(self, integration_id: str, config: dict) -> Integration: return Integration(**self._client.patch(f"{self._base}/{integration_id}", json={"config": config}))
    def test_connection(self, integration_id: str) -> dict: return self._client.post(f"{self._base}/{integration_id}/test")
    def list_webhooks(self, integration_id: str | None = None) -> list[dict]: path = f"{self._base}/{integration_id}/webhooks" if integration_id else "/v1/webhooks"; return self._client.get(path)
    def create_webhook(self, integration_id: str, url: str, events: list[str]) -> dict: return self._client.post(f"{self._base}/{integration_id}/webhooks", json={"url": url, "events": events})
    def remove_webhook(self, webhook_id: str) -> None: self._client.delete(f"/v1/webhooks/{webhook_id}")
    def list_deliveries(self, webhook_id: str, **params: Any) -> dict: return self._client.get(f"/v1/webhooks/{webhook_id}/deliveries", params={k: v for k, v in params.items() if v is not None})
