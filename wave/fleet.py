"""WAVE SDK - Fleet API. Desktop Node device fleet management."""
from __future__ import annotations
import time
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class FleetNode(BaseModel):
    id: str; organization_id: str; name: str; status: str; health: str; ip_address: str | None = None; version: str | None = None; os: str | None = None; cpu_usage: float = 0; memory_usage: float = 0; device_count: int = 0; last_seen_at: str | None = None; created_at: str; updated_at: str

class NodeDevice(BaseModel):
    id: str; node_id: str; name: str; type: str; status: str; driver_version: str | None = None

class FleetAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/fleet/nodes"
    def list(self, **params: Any) -> dict: return self._client.get(self._base, params={k: v for k, v in params.items() if v is not None})
    def get(self, node_id: str) -> FleetNode: return FleetNode(**self._client.get(f"{self._base}/{node_id}"))
    def register(self, name: str, os: str, version: str, **kwargs: Any) -> FleetNode: return FleetNode(**self._client.post(self._base, json={"name": name, "os": os, "version": version, **kwargs}))
    def update(self, node_id: str, **kwargs: Any) -> FleetNode: return FleetNode(**self._client.patch(f"{self._base}/{node_id}", json=kwargs))
    def deregister(self, node_id: str) -> None: self._client.delete(f"{self._base}/{node_id}")
    def get_health(self, node_id: str) -> dict: return self._client.get(f"{self._base}/{node_id}/health")
    def list_devices(self, node_id: str) -> list[NodeDevice]: return [NodeDevice(**d) for d in self._client.get(f"{self._base}/{node_id}/devices")]
    def send_command(self, node_id: str, command_type: str, params: dict | None = None) -> dict: return self._client.post(f"{self._base}/{node_id}/commands", json={"type": command_type, "params": params})
    def get_metrics(self, node_id: str) -> dict: return self._client.get(f"{self._base}/{node_id}/metrics")
    def wait_for_online(self, node_id: str, poll_interval: float = 5.0, timeout: float = 120.0) -> FleetNode:
        start = time.time()
        while time.time() - start < timeout:
            n = self.get(node_id)
            if n.status == "online": return n
            time.sleep(poll_interval)
        raise TimeoutError(f"Node did not come online within {timeout}s")
