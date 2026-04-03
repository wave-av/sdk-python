"""WAVE SDK - Prism API. Virtual Device Bridge for network AV to USB."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class VirtualDevice(BaseModel):
    id: str; organization_id: str; name: str; type: str; status: str; source_protocol: str; source_endpoint: str; node_id: str; resolution: dict | None = None; frame_rate: int | None = None; health_score: float = 100; ptz_enabled: bool = False; created_at: str; updated_at: str

class PresetMapping(BaseModel):
    id: str; device_id: str; slot_number: int; preset_name: str; preset_token: str; protocol: str; transition_speed: float = 1.0; created_at: str; updated_at: str

class PrismAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/prism"
    def create_device(self, name: str, type: str, source_protocol: str, source_endpoint: str, node_id: str, **kwargs: Any) -> VirtualDevice: return VirtualDevice(**self._client.post(f"{self._base}/devices", json={"name": name, "type": type, "source_protocol": source_protocol, "source_endpoint": source_endpoint, "node_id": node_id, **kwargs}))
    def get_device(self, device_id: str) -> VirtualDevice: return VirtualDevice(**self._client.get(f"{self._base}/devices/{device_id}"))
    def update_device(self, device_id: str, **kwargs: Any) -> VirtualDevice: return VirtualDevice(**self._client.patch(f"{self._base}/devices/{device_id}", json=kwargs))
    def remove_device(self, device_id: str) -> None: self._client.delete(f"{self._base}/devices/{device_id}")
    def list_devices(self, **params: Any) -> dict: return self._client.get(f"{self._base}/devices", params={k: v for k, v in params.items() if v is not None})
    def start_device(self, device_id: str) -> VirtualDevice: return VirtualDevice(**self._client.post(f"{self._base}/devices/{device_id}/start"))
    def stop_device(self, device_id: str) -> VirtualDevice: return VirtualDevice(**self._client.post(f"{self._base}/devices/{device_id}/stop"))
    def get_health(self, device_id: str) -> dict: return self._client.get(f"{self._base}/devices/{device_id}/health")
    def discover_sources(self, **kwargs: Any) -> list[dict]: return self._client.post(f"{self._base}/discovery", json=kwargs if kwargs else None)
    def get_presets(self, device_id: str) -> list[PresetMapping]: return [PresetMapping(**p) for p in self._client.get(f"{self._base}/devices/{device_id}/presets")]
    def set_preset(self, device_id: str, slot_number: int, preset_name: str, preset_token: str, protocol: str, **kwargs: Any) -> PresetMapping: return PresetMapping(**self._client.put(f"{self._base}/devices/{device_id}/presets", json={"slot_number": slot_number, "preset_name": preset_name, "preset_token": preset_token, "protocol": protocol, **kwargs}))
    def remove_preset(self, device_id: str, slot_number: int) -> None: self._client.delete(f"{self._base}/devices/{device_id}/presets/{slot_number}")
    def recall_preset(self, device_id: str, slot_number: int) -> None: self._client.post(f"{self._base}/devices/{device_id}/presets/{slot_number}/recall")
