"""WAVE SDK - Scene API. AI scene detection, shot classification, and visual analysis."""
from __future__ import annotations
import time
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class Scene(BaseModel):
    id: str; start_time: float; end_time: float; scene_type: str; shot_type: str | None = None; confidence: float; labels: list[str] | None = None; thumbnail_url: str | None = None

class Shot(BaseModel):
    id: str; scene_id: str; start_time: float; end_time: float; type: str; confidence: float

class SceneDetection(BaseModel):
    id: str; asset_id: str; status: str; scene_count: int = 0; shot_count: int = 0; scenes: list[Scene] | None = None; created_at: str; updated_at: str

class SceneAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/scene"
    def detect(self, media_id: str, media_type: str = "video", **kwargs: Any) -> SceneDetection: return SceneDetection(**self._client.post(f"{self._base}/detect", json={"media_id": media_id, "media_type": media_type, **kwargs}))
    def get_detection(self, detection_id: str) -> SceneDetection: return SceneDetection(**self._client.get(f"{self._base}/{detection_id}"))
    def list_detections(self, **params: Any) -> dict: return self._client.get(self._base, params={k: v for k, v in params.items() if v is not None})
    def remove_detection(self, detection_id: str) -> None: self._client.delete(f"{self._base}/{detection_id}")
    def get_scenes(self, detection_id: str) -> list[Scene]: return [Scene(**s) for s in self._client.get(f"{self._base}/{detection_id}/scenes")]
    def get_scene(self, detection_id: str, scene_id: str) -> Scene: return Scene(**self._client.get(f"{self._base}/{detection_id}/scenes/{scene_id}"))
    def update_scene(self, detection_id: str, scene_id: str, **kwargs: Any) -> Scene: return Scene(**self._client.patch(f"{self._base}/{detection_id}/scenes/{scene_id}", json=kwargs))
    def get_scene_at_time(self, detection_id: str, time_seconds: float) -> Scene: return Scene(**self._client.get(f"{self._base}/{detection_id}/at-time", params={"time": time_seconds}))
    def get_all_shots(self, detection_id: str) -> list[Shot]: return [Shot(**s) for s in self._client.get(f"{self._base}/{detection_id}/shots")]
    def get_shots(self, detection_id: str, scene_id: str) -> list[Shot]: return [Shot(**s) for s in self._client.get(f"{self._base}/{detection_id}/scenes/{scene_id}/shots")]
    def detect_boundaries(self, detection_id: str) -> list[dict]: return self._client.get(f"{self._base}/{detection_id}/boundaries")
    def get_boundaries(self, detection_id: str) -> list[dict]: return self._client.get(f"{self._base}/{detection_id}/boundaries")
    def split_scene(self, detection_id: str, scene_id: str, split_time: float) -> list[Scene]: return [Scene(**s) for s in self._client.post(f"{self._base}/{detection_id}/scenes/{scene_id}/split", json={"split_time": split_time})]
    def merge_scenes(self, detection_id: str, scene_ids: list[str]) -> Scene: return Scene(**self._client.post(f"{self._base}/{detection_id}/merge", json={"scene_ids": scene_ids}))
    def find_similar_scenes(self, detection_id: str, scene_id: str, **params: Any) -> list[Scene]: return [Scene(**s) for s in self._client.get(f"{self._base}/{detection_id}/scenes/{scene_id}/similar", params={k: v for k, v in params.items() if v is not None})]
    def compare_scenes(self, detection_ids: list[str]) -> dict: return self._client.post(f"{self._base}/compare", json={"detection_ids": detection_ids})
    def generate_thumbnails(self, detection_id: str) -> SceneDetection: return SceneDetection(**self._client.post(f"{self._base}/{detection_id}/thumbnails"))
    def get_summary(self, detection_id: str) -> dict: return self._client.get(f"{self._base}/{detection_id}/summary")
    def get_timeline(self, detection_id: str) -> dict: return self._client.get(f"{self._base}/{detection_id}/timeline")
    def export_detection(self, detection_id: str, format: str = "json") -> dict: return self._client.get(f"{self._base}/{detection_id}/export", params={"format": format})
    def wait_for_ready(self, detection_id: str, poll_interval: float = 3.0, timeout: float = 600.0) -> SceneDetection:
        start = time.time()
        while time.time() - start < timeout:
            d = self.get_detection(detection_id)
            if d.status == "ready": return d
            if d.status == "failed": raise RuntimeError("Scene detection failed")
            time.sleep(poll_interval)
        raise TimeoutError(f"Scene detection timed out after {timeout}s")
