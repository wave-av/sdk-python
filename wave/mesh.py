"""WAVE SDK - Mesh API. Multi-region infrastructure failover."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class MeshRegion(BaseModel):
    id: str; name: str; provider: str; location: str; status: str; latency_ms: int; capacity_percent: float; stream_count: int; viewer_count: int; is_primary: bool; created_at: str; updated_at: str

class FailoverPolicy(BaseModel):
    id: str; organization_id: str; name: str; strategy: str; primary_region: str; fallback_regions: list[str]; auto_failback: bool = True; created_at: str; updated_at: str

class MeshAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/mesh"
    def list_regions(self, **params: Any) -> dict: return self._client.get(f"{self._base}/regions", params={k: v for k, v in params.items() if v is not None})
    def get_region(self, region_id: str) -> MeshRegion: return MeshRegion(**self._client.get(f"{self._base}/regions/{region_id}"))
    def get_region_health(self, region_id: str) -> dict: return self._client.get(f"{self._base}/regions/{region_id}/health")
    def list_peers(self, region_id: str | None = None) -> list[dict]: path = f"{self._base}/regions/{region_id}/peers" if region_id else f"{self._base}/peers"; return self._client.get(path)
    def add_peer(self, region_id: str, endpoint: str) -> dict: return self._client.post(f"{self._base}/regions/{region_id}/peers", json={"endpoint": endpoint})
    def remove_peer(self, peer_id: str) -> None: self._client.delete(f"{self._base}/peers/{peer_id}")
    def create_policy(self, name: str, strategy: str, primary_region: str, fallback_regions: list[str], **kwargs: Any) -> FailoverPolicy: return FailoverPolicy(**self._client.post(f"{self._base}/policies", json={"name": name, "strategy": strategy, "primary_region": primary_region, "fallback_regions": fallback_regions, **kwargs}))
    def list_policies(self, **params: Any) -> dict: return self._client.get(f"{self._base}/policies", params={k: v for k, v in params.items() if v is not None})
    def trigger_failover(self, policy_id: str, target_region: str) -> dict: return self._client.post(f"{self._base}/policies/{policy_id}/failover", json={"target_region": target_region})
    def get_replication_status(self) -> list[dict]: return self._client.get(f"{self._base}/replication")
    def get_topology(self) -> dict: return self._client.get(f"{self._base}/topology")
