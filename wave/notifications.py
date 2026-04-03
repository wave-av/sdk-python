"""WAVE SDK - Notifications API. User notifications, preferences, and delivery channels."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class Notification(BaseModel):
    id: str; user_id: str; type: str; title: str; body: str; status: str; priority: str; channel: str; action_url: str | None = None; read_at: str | None = None; created_at: str; updated_at: str

class NotificationsAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/notifications"
    def list(self, **params: Any) -> dict: return self._client.get(self._base, params={k: v for k, v in params.items() if v is not None})
    def get(self, notification_id: str) -> Notification: return Notification(**self._client.get(f"{self._base}/{notification_id}"))
    def mark_as_read(self, notification_id: str) -> Notification: return Notification(**self._client.post(f"{self._base}/{notification_id}/read"))
    def mark_all_read(self) -> dict: return self._client.post(f"{self._base}/mark-all-read")
    def archive(self, notification_id: str) -> Notification: return Notification(**self._client.post(f"{self._base}/{notification_id}/archive"))
    def remove(self, notification_id: str) -> None: self._client.delete(f"{self._base}/{notification_id}")
    def get_unread_count(self) -> dict: return self._client.get(f"{self._base}/unread-count")
    def get_preferences(self) -> dict: return self._client.get(f"{self._base}/preferences")
    def update_preferences(self, **prefs: Any) -> dict: return self._client.patch(f"{self._base}/preferences", json=prefs)
