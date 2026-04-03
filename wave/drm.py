"""WAVE SDK - DRM API. Content protection with Widevine, FairPlay, and PlayReady."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class DRMPolicy(BaseModel):
    id: str; organization_id: str; name: str; providers: list[str]; allow_offline: bool = False; max_devices: int = 1; output_protection: str = "none"; persistent_license: bool = False; created_at: str; updated_at: str

class DRMLicense(BaseModel):
    id: str; policy_id: str; asset_id: str; user_id: str; provider: str; status: str; expires_at: str | None = None; playback_count: int = 0; created_at: str; updated_at: str

class DrmAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/drm"
    def create_policy(self, name: str, providers: list[str], **kwargs: Any) -> DRMPolicy: return DRMPolicy(**self._client.post(f"{self._base}/policies", json={"name": name, "providers": providers, **kwargs}))
    def get_policy(self, policy_id: str) -> DRMPolicy: return DRMPolicy(**self._client.get(f"{self._base}/policies/{policy_id}"))
    def list_policies(self, **params: Any) -> dict: return self._client.get(f"{self._base}/policies", params={k: v for k, v in params.items() if v is not None})
    def update_policy(self, policy_id: str, **kwargs: Any) -> DRMPolicy: return DRMPolicy(**self._client.patch(f"{self._base}/policies/{policy_id}", json=kwargs))
    def remove_policy(self, policy_id: str) -> None: self._client.delete(f"{self._base}/policies/{policy_id}")
    def get_certificate(self, provider: str) -> dict: return self._client.get(f"{self._base}/certificate/{provider}")
    def issue_license(self, asset_id: str, policy_id: str, device_id: str | None = None) -> DRMLicense: return DRMLicense(**self._client.post(f"{self._base}/license", json={"asset_id": asset_id, "policy_id": policy_id, "device_id": device_id}))
    def revoke_license(self, license_id: str) -> DRMLicense: return DRMLicense(**self._client.post(f"{self._base}/license/{license_id}/revoke"))
    def list_licenses(self, **params: Any) -> dict: return self._client.get(f"{self._base}/licenses", params={k: v for k, v in params.items() if v is not None})
