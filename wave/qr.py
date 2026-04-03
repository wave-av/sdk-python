"""WAVE SDK - QR API. Dynamic QR code generation and analytics."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class QRCode(BaseModel):
    id: str; organization_id: str; type: str; content: str; short_url: str; image_url: str; scan_count: int = 0; status: str = "active"; expires_at: str | None = None; created_at: str; updated_at: str

class QrAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/qr"
    def create(self, type: str, content: str, **kwargs: Any) -> QRCode: return QRCode(**self._client.post(self._base, json={"type": type, "content": content, **kwargs}))
    def get(self, qr_id: str) -> QRCode: return QRCode(**self._client.get(f"{self._base}/{qr_id}"))
    def update(self, qr_id: str, **kwargs: Any) -> QRCode: return QRCode(**self._client.patch(f"{self._base}/{qr_id}", json=kwargs))
    def remove(self, qr_id: str) -> None: self._client.delete(f"{self._base}/{qr_id}")
    def list(self, **params: Any) -> dict: return self._client.get(self._base, params={k: v for k, v in params.items() if v is not None})
    def get_analytics(self, qr_id: str, **params: Any) -> dict: return self._client.get(f"{self._base}/{qr_id}/analytics", params={k: v for k, v in params.items() if v is not None})
    def create_batch(self, items: list[dict]) -> list[QRCode]: return [QRCode(**q) for q in self._client.post(f"{self._base}/batch", json={"items": items})]
    def get_image(self, qr_id: str, format: str = "png", size: int | None = None) -> dict: return self._client.get(f"{self._base}/{qr_id}/image", params={"format": format, **({"size": size} if size else {})})
