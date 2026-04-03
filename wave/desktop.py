"""WAVE SDK - Desktop API. Desktop Node application management."""
from __future__ import annotations
from typing import Any
from wave.client import WaveClient

class DesktopAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/desktop"
    def get_info(self, node_id: str) -> dict: return self._client.get(f"{self._base}/nodes/{node_id}")
    def get_status(self, node_id: str) -> dict: return self._client.get(f"{self._base}/nodes/{node_id}/status")
    def list_devices(self, node_id: str) -> list[dict]: return self._client.get(f"{self._base}/nodes/{node_id}/devices")
    def configure(self, node_id: str, **config: Any) -> dict: return self._client.patch(f"{self._base}/nodes/{node_id}/config", json=config)
    def get_config(self, node_id: str) -> dict: return self._client.get(f"{self._base}/nodes/{node_id}/config")
    def get_logs(self, node_id: str, **params: Any) -> list[dict]: return self._client.get(f"{self._base}/nodes/{node_id}/logs", params={k: v for k, v in params.items() if v is not None})
    def get_performance(self, node_id: str) -> dict: return self._client.get(f"{self._base}/nodes/{node_id}/performance")
    def check_for_update(self, node_id: str) -> dict: return self._client.get(f"{self._base}/nodes/{node_id}/updates")
    def install_update(self, node_id: str) -> dict: return self._client.post(f"{self._base}/nodes/{node_id}/updates/install")
    def restart(self, node_id: str) -> dict: return self._client.post(f"{self._base}/nodes/{node_id}/restart")
