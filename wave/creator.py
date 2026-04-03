"""WAVE SDK - Creator API. Monetization, subscriptions, tips, and payouts."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class CreatorProfile(BaseModel):
    id: str; user_id: str; display_name: str; subscriber_count: int = 0; total_revenue_cents: int = 0; verified: bool = False; tier: str = "starter"; created_at: str; updated_at: str

class CreatorAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/creators"
    def get_profile(self, creator_id: str) -> CreatorProfile: return CreatorProfile(**self._client.get(f"{self._base}/{creator_id}"))
    def update_profile(self, creator_id: str, **kwargs: Any) -> CreatorProfile: return CreatorProfile(**self._client.patch(f"{self._base}/{creator_id}", json=kwargs))
    def get_revenue(self, creator_id: str, **params: Any) -> dict: return self._client.get(f"{self._base}/{creator_id}/revenue", params={k: v for k, v in params.items() if v is not None})
    def list_subscriptions(self, creator_id: str, **params: Any) -> dict: return self._client.get(f"{self._base}/{creator_id}/subscriptions", params={k: v for k, v in params.items() if v is not None})
    def list_tips(self, creator_id: str, **params: Any) -> dict: return self._client.get(f"{self._base}/{creator_id}/tips", params={k: v for k, v in params.items() if v is not None})
    def create_tip_jar(self, creator_id: str, enabled: bool = True, **kwargs: Any) -> dict: return self._client.post(f"{self._base}/{creator_id}/tip-jar", json={"enabled": enabled, **kwargs})
    def list_payouts(self, creator_id: str, **params: Any) -> dict: return self._client.get(f"{self._base}/{creator_id}/payouts", params={k: v for k, v in params.items() if v is not None})
    def request_payout(self, creator_id: str, amount_cents: int, method: str) -> dict: return self._client.post(f"{self._base}/{creator_id}/payouts", json={"amount_cents": amount_cents, "method": method})
    def get_analytics(self, creator_id: str, **params: Any) -> dict: return self._client.get(f"{self._base}/{creator_id}/analytics", params={k: v for k, v in params.items() if v is not None})
