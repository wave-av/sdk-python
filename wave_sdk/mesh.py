"""WAVE SDK - Mesh API. The WAVE mesh overlay's control plane at ``/v1/mesh``.

Every ``/v1/mesh`` request must carry an ``x-wave-node`` header: the name of the node the call
is made for (a target selector the server scopes to your organization, not a credential). Set it
once with ``client.mesh.node = "studio-a"`` (or ``MeshAPI(client, node=...)``), or pass
``node=`` to :meth:`MeshAPI.list_peers`. A call without a node raises ``ValueError`` locally
instead of a 400 from the server.

``list_peers()`` (``GET /v1/mesh/peers``) is served. The region / policy / replication /
topology methods predate the current mesh API and are answered 404 by it today; they raise
:class:`~wave_sdk.client.WaveError` with the server's code.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wave_sdk.client import WaveClient

NODE_HEADER = "x-wave-node"


class MeshRegion(BaseModel):
    id: str; name: str; provider: str; location: str; status: str; latency_ms: int; capacity_percent: float; stream_count: int; viewer_count: int; is_primary: bool; created_at: str; updated_at: str

class FailoverPolicy(BaseModel):
    id: str; organization_id: str; name: str; strategy: str; primary_region: str; fallback_regions: list[str]; auto_failback: bool = True; created_at: str; updated_at: str

class MeshAPI:
    def __init__(self, client: WaveClient, node: str | None = None):
        self._client = client
        self._base = "/v1/mesh"
        self.node = node

    def _headers(self, node: str | None = None) -> dict[str, str]:
        name = node or self.node
        if not name:
            raise ValueError(
                "WAVE mesh: every /v1/mesh request needs an x-wave-node target; "
                "set client.mesh.node = '<node-name>' or pass node='<node-name>'"
            )
        return {NODE_HEADER: name}

    def _get(self, path: str, params: dict[str, Any] | None = None, node: str | None = None) -> Any:
        return self._client.get(path, params=params, headers=self._headers(node))

    def _post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return self._client.post(path, json=json, headers=self._headers())

    def list_peers(self, region_id: str | None = None, node: str | None = None) -> dict:
        """``GET /v1/mesh/peers``: the org's mesh peers (``{"org", "count", "peers": [...]}``)."""
        path = f"{self._base}/regions/{region_id}/peers" if region_id else f"{self._base}/peers"
        result: dict = self._get(path, node=node)
        return result
    def list_regions(self, **params: Any) -> dict: return self._get(f"{self._base}/regions", params={k: v for k, v in params.items() if v is not None})
    def get_region(self, region_id: str) -> MeshRegion: return MeshRegion(**self._get(f"{self._base}/regions/{region_id}"))
    def get_region_health(self, region_id: str) -> dict: return self._get(f"{self._base}/regions/{region_id}/health")
    def add_peer(self, region_id: str, endpoint: str) -> dict: return self._post(f"{self._base}/regions/{region_id}/peers", json={"endpoint": endpoint})
    def remove_peer(self, peer_id: str) -> None: self._client.delete(f"{self._base}/peers/{peer_id}", headers=self._headers())
    def create_policy(self, name: str, strategy: str, primary_region: str, fallback_regions: list[str], **kwargs: Any) -> FailoverPolicy: return FailoverPolicy(**self._post(f"{self._base}/policies", json={"name": name, "strategy": strategy, "primary_region": primary_region, "fallback_regions": fallback_regions, **kwargs}))
    def list_policies(self, **params: Any) -> dict: return self._get(f"{self._base}/policies", params={k: v for k, v in params.items() if v is not None})
    def trigger_failover(self, policy_id: str, target_region: str) -> dict: return self._post(f"{self._base}/policies/{policy_id}/failover", json={"target_region": target_region})
    def get_replication_status(self) -> list[dict]: return self._get(f"{self._base}/replication")
    def get_topology(self) -> dict: return self._get(f"{self._base}/topology")
