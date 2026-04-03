"""WAVE SDK - Edge API. Edge computing and CDN operations."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class EdgeNode(BaseModel):
    id: str; name: str; region: str; provider: str; status: str; latency_ms: int; capacity_percent: float; active_workers: int; bandwidth_mbps: float; created_at: str; updated_at: str

class EdgeWorker(BaseModel):
    id: str; name: str; node_id: str; status: str; runtime: str; invocations: int; last_deployed_at: str | None = None; created_at: str; updated_at: str

class EdgeAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/edge"
    def list_nodes(self, **params: Any) -> dict: return self._client.get(f"{self._base}/nodes", params={k: v for k, v in params.items() if v is not None})
    def get_node(self, node_id: str) -> EdgeNode: return EdgeNode(**self._client.get(f"{self._base}/nodes/{node_id}"))
    def get_node_metrics(self, node_id: str) -> dict: return self._client.get(f"{self._base}/nodes/{node_id}/metrics")
    def deploy_worker(self, name: str, runtime: str, script: str, routes: list[str], **kwargs: Any) -> EdgeWorker: return EdgeWorker(**self._client.post(f"{self._base}/workers", json={"name": name, "runtime": runtime, "script": script, "routes": routes, **kwargs}))
    def get_worker(self, worker_id: str) -> EdgeWorker: return EdgeWorker(**self._client.get(f"{self._base}/workers/{worker_id}"))
    def remove_worker(self, worker_id: str) -> None: self._client.delete(f"{self._base}/workers/{worker_id}")
    def list_workers(self, **params: Any) -> dict: return self._client.get(f"{self._base}/workers", params={k: v for k, v in params.items() if v is not None})
    def purge_cache(self, patterns: list[str]) -> dict: return self._client.post(f"{self._base}/cache/purge", json={"patterns": patterns})
    def list_pops(self) -> list[dict]: return self._client.get(f"{self._base}/pops")
    def get_latency_map(self) -> dict: return self._client.get(f"{self._base}/latency-map")
