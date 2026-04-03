"""WAVE SDK - USB API. USB device relay and management."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class USBDevice(BaseModel):
    id: str; node_id: str; name: str; vendor_id: str; product_id: str; device_class: str; status: str; manufacturer: str | None = None; speed: str; capabilities: list[str] | None = None; connected_at: str; updated_at: str

class UsbAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/usb"
    def list(self, **params: Any) -> dict: return self._client.get(f"{self._base}/devices", params={k: v for k, v in params.items() if v is not None})
    def get(self, device_id: str) -> USBDevice: return USBDevice(**self._client.get(f"{self._base}/devices/{device_id}"))
    def claim(self, device_id: str, **kwargs: Any) -> USBDevice: return USBDevice(**self._client.post(f"{self._base}/devices/{device_id}/claim", json=kwargs if kwargs else None))
    def release(self, device_id: str) -> USBDevice: return USBDevice(**self._client.post(f"{self._base}/devices/{device_id}/release"))
    def get_capabilities(self, device_id: str) -> dict: return self._client.get(f"{self._base}/devices/{device_id}/capabilities")
    def list_by_node(self, node_id: str, **params: Any) -> dict: return self._client.get(f"{self._base}/nodes/{node_id}/devices", params={k: v for k, v in params.items() if v is not None})
    def configure(self, device_id: str, **config: Any) -> USBDevice: return USBDevice(**self._client.patch(f"{self._base}/devices/{device_id}/config", json=config))
