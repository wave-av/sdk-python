"""WAVE SDK - Mesh API. The WAVE mesh overlay's control plane at ``/v1/mesh``.

Every ``/v1/mesh`` request must carry an ``x-wave-node`` header: the name of the node the call
is made for (a target selector the server scopes to your organization, not a credential). Set it
once with ``client.mesh.node = "studio-a"`` (or ``MeshAPI(client, node=...)``), or pass ``node=``
to any method for one call. Every method, reads and mutations alike, builds the header before it
sends anything: a call without a node raises ``ValueError`` locally instead of a 400 from the
server, and so does a node name containing a line break.

``list_peers()`` (``GET /v1/mesh/peers``) is served. The region / policy / replication /
topology methods predate the current mesh API and are answered 404 by it today; they raise
:class:`~wave_sdk.client.WaveError` with the server's code.

The mutations (``add_peer``, ``remove_peer``, ``create_policy``, ``trigger_failover``) are sent
once: a retry after the server applied the change would add a second peer or policy, or fail
over twice.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wave_sdk.client import WaveClient, path_segment

NODE_HEADER = "x-wave-node"

_seg = path_segment


def _clean(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if v is not None}


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
        if not isinstance(name, str) or "\r" in name or "\n" in name:
            raise ValueError("WAVE mesh: a node name must be a single-line string")
        return {NODE_HEADER: name}

    def _get(self, path: str, params: dict[str, Any] | None = None, node: str | None = None) -> Any:
        return self._client.get(path, params=params, headers=self._headers(node))

    def _post(self, path: str, json: dict[str, Any] | None = None, node: str | None = None) -> Any:
        return self._client.post(path, json=json, headers=self._headers(node), no_retry=True)

    def _delete(self, path: str, node: str | None = None) -> Any:
        return self._client.delete(path, headers=self._headers(node), no_retry=True)

    def list_peers(self, region_id: str | None = None, node: str | None = None) -> dict[str, Any]:
        """``GET /v1/mesh/peers``: the org's mesh peers (``{"org", "count", "peers": [...]}``)."""
        path = f"{self._base}/regions/{_seg(region_id)}/peers" if region_id else f"{self._base}/peers"
        result: dict[str, Any] = self._get(path, node=node)
        return result

    def list_regions(self, *, node: str | None = None, **params: Any) -> dict[str, Any]:
        result: dict[str, Any] = self._get(f"{self._base}/regions", params=_clean(params), node=node)
        return result

    def get_region(self, region_id: str, *, node: str | None = None) -> MeshRegion:
        return MeshRegion(**self._get(f"{self._base}/regions/{_seg(region_id)}", node=node))

    def get_region_health(self, region_id: str, *, node: str | None = None) -> dict[str, Any]:
        result: dict[str, Any] = self._get(f"{self._base}/regions/{_seg(region_id)}/health", node=node)
        return result

    def add_peer(self, region_id: str, endpoint: str, *, node: str | None = None) -> dict[str, Any]:
        result: dict[str, Any] = self._post(f"{self._base}/regions/{_seg(region_id)}/peers", json={"endpoint": endpoint}, node=node)
        return result

    def remove_peer(self, peer_id: str, *, node: str | None = None) -> None:
        self._delete(f"{self._base}/peers/{_seg(peer_id)}", node=node)

    def create_policy(self, name: str, strategy: str, primary_region: str, fallback_regions: list[str], *, node: str | None = None, **kwargs: Any) -> FailoverPolicy:
        body = {"name": name, "strategy": strategy, "primary_region": primary_region, "fallback_regions": fallback_regions, **kwargs}
        return FailoverPolicy(**self._post(f"{self._base}/policies", json=body, node=node))

    def list_policies(self, *, node: str | None = None, **params: Any) -> dict[str, Any]:
        result: dict[str, Any] = self._get(f"{self._base}/policies", params=_clean(params), node=node)
        return result

    def trigger_failover(self, policy_id: str, target_region: str, *, node: str | None = None) -> dict[str, Any]:
        result: dict[str, Any] = self._post(f"{self._base}/policies/{_seg(policy_id)}/failover", json={"target_region": target_region}, node=node)
        return result

    def get_replication_status(self, *, node: str | None = None) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = self._get(f"{self._base}/replication", node=node)
        return result

    def get_topology(self, *, node: str | None = None) -> dict[str, Any]:
        result: dict[str, Any] = self._get(f"{self._base}/topology", node=node)
        return result
