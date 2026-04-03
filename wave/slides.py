"""WAVE SDK - Slides API. Presentation to video conversion."""
from __future__ import annotations
import time
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class Conversion(BaseModel):
    id: str; organization_id: str; title: str; status: str; input_format: str; input_url: str; output_url: str | None = None; slide_count: int = 0; duration_seconds: float | None = None; progress_percent: int = 0; error: str | None = None; created_at: str; updated_at: str

class SlidesAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/slides"
    def convert(self, title: str, input_url: str, input_format: str, **kwargs: Any) -> Conversion: return Conversion(**self._client.post(self._base, json={"title": title, "input_url": input_url, "input_format": input_format, **kwargs}))
    def get(self, conversion_id: str) -> Conversion: return Conversion(**self._client.get(f"{self._base}/{conversion_id}"))
    def list(self, **params: Any) -> dict: return self._client.get(self._base, params={k: v for k, v in params.items() if v is not None})
    def remove(self, conversion_id: str) -> None: self._client.delete(f"{self._base}/{conversion_id}")
    def add_narration(self, conversion_id: str, narrations: list[dict]) -> Conversion: return Conversion(**self._client.post(f"{self._base}/{conversion_id}/narration", json={"narrations": narrations}))
    def wait_for_ready(self, conversion_id: str, poll_interval: float = 3.0, timeout: float = 600.0) -> Conversion:
        start = time.time()
        while time.time() - start < timeout:
            c = self.get(conversion_id)
            if c.status == "ready": return c
            if c.status == "failed": raise RuntimeError(f"Conversion failed: {c.error}")
            time.sleep(poll_interval)
        raise TimeoutError(f"Conversion timed out after {timeout}s")
