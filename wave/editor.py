"""WAVE SDK - Editor API. Video editing with tracks, transitions, effects, and rendering."""
from __future__ import annotations
import time
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class EditorProject(BaseModel):
    id: str; organization_id: str; title: str; status: str; duration: float = 0; track_count: int = 0; created_at: str; updated_at: str

class Track(BaseModel):
    id: str; project_id: str; name: str; type: str; sort_order: int = 0; muted: bool = False; locked: bool = False

class TimelineElement(BaseModel):
    id: str; track_id: str; type: str; source_url: str | None = None; start_time: float; end_time: float; in_point: float = 0; out_point: float = 0

class RenderJob(BaseModel):
    id: str; project_id: str; status: str; progress_percent: int = 0; output_url: str | None = None; error: str | None = None; created_at: str

class EditorAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/editor/projects"
    def create_project(self, title: str, **kwargs: Any) -> EditorProject: return EditorProject(**self._client.post(self._base, json={"title": title, **kwargs}))
    def get_project(self, project_id: str) -> EditorProject: return EditorProject(**self._client.get(f"{self._base}/{project_id}"))
    def update_project(self, project_id: str, **kwargs: Any) -> EditorProject: return EditorProject(**self._client.patch(f"{self._base}/{project_id}", json=kwargs))
    def remove_project(self, project_id: str) -> None: self._client.delete(f"{self._base}/{project_id}")
    def list_projects(self, **params: Any) -> dict: return self._client.get(self._base, params={k: v for k, v in params.items() if v is not None})
    def duplicate_project(self, project_id: str) -> EditorProject: return EditorProject(**self._client.post(f"{self._base}/{project_id}/duplicate"))
    def add_track(self, project_id: str, name: str, type: str = "video", **kwargs: Any) -> Track: return Track(**self._client.post(f"{self._base}/{project_id}/tracks", json={"name": name, "type": type, **kwargs}))
    def update_track(self, project_id: str, track_id: str, **kwargs: Any) -> Track: return Track(**self._client.patch(f"{self._base}/{project_id}/tracks/{track_id}", json=kwargs))
    def remove_track(self, project_id: str, track_id: str) -> None: self._client.delete(f"{self._base}/{project_id}/tracks/{track_id}")
    def add_element(self, project_id: str, track_id: str, type: str, start_time: float, end_time: float, **kwargs: Any) -> TimelineElement: return TimelineElement(**self._client.post(f"{self._base}/{project_id}/tracks/{track_id}/elements", json={"type": type, "start_time": start_time, "end_time": end_time, **kwargs}))
    def update_element(self, project_id: str, element_id: str, **kwargs: Any) -> TimelineElement: return TimelineElement(**self._client.patch(f"{self._base}/{project_id}/elements/{element_id}", json=kwargs))
    def remove_element(self, project_id: str, element_id: str) -> None: self._client.delete(f"{self._base}/{project_id}/elements/{element_id}")
    def move_element(self, project_id: str, element_id: str, track_id: str, start_time: float) -> TimelineElement: return TimelineElement(**self._client.post(f"{self._base}/{project_id}/elements/{element_id}/move", json={"track_id": track_id, "start_time": start_time}))
    def trim_element(self, project_id: str, element_id: str, in_point: float, out_point: float) -> TimelineElement: return TimelineElement(**self._client.post(f"{self._base}/{project_id}/elements/{element_id}/trim", json={"in_point": in_point, "out_point": out_point}))
    def add_transition(self, project_id: str, type: str, element_a_id: str, element_b_id: str, duration_ms: int = 500) -> dict: return self._client.post(f"{self._base}/{project_id}/transitions", json={"type": type, "element_a_id": element_a_id, "element_b_id": element_b_id, "duration_ms": duration_ms})
    def update_transition(self, project_id: str, transition_id: str, **kwargs: Any) -> dict: return self._client.patch(f"{self._base}/{project_id}/transitions/{transition_id}", json=kwargs)
    def remove_transition(self, project_id: str, transition_id: str) -> None: self._client.delete(f"{self._base}/{project_id}/transitions/{transition_id}")
    def add_effect(self, project_id: str, element_id: str, type: str, **kwargs: Any) -> dict: return self._client.post(f"{self._base}/{project_id}/elements/{element_id}/effects", json={"type": type, **kwargs})
    def update_effect(self, project_id: str, effect_id: str, **kwargs: Any) -> dict: return self._client.patch(f"{self._base}/{project_id}/effects/{effect_id}", json=kwargs)
    def remove_effect(self, project_id: str, effect_id: str) -> None: self._client.delete(f"{self._base}/{project_id}/effects/{effect_id}")
    def get_preview_frame(self, project_id: str, time_seconds: float) -> dict: return self._client.get(f"{self._base}/{project_id}/preview/frame", params={"time": time_seconds})
    def get_preview_segment(self, project_id: str, start: float, end: float) -> dict: return self._client.get(f"{self._base}/{project_id}/preview/segment", params={"start": start, "end": end})
    def render(self, project_id: str, **kwargs: Any) -> RenderJob: return RenderJob(**self._client.post(f"{self._base}/{project_id}/render", json=kwargs if kwargs else None))
    def get_render_job(self, job_id: str) -> RenderJob: return RenderJob(**self._client.get(f"/v1/editor/renders/{job_id}"))
    def list_render_jobs(self, project_id: str, **params: Any) -> dict: return self._client.get(f"{self._base}/{project_id}/renders", params={k: v for k, v in params.items() if v is not None})
    def cancel_render_job(self, job_id: str) -> None: self._client.post(f"/v1/editor/renders/{job_id}/cancel")
    def wait_for_render(self, job_id: str, poll_interval: float = 3.0, timeout: float = 600.0) -> RenderJob:
        start = time.time()
        while time.time() - start < timeout:
            j = self.get_render_job(job_id)
            if j.status == "ready": return j
            if j.status == "failed": raise RuntimeError(f"Render failed: {j.error}")
            time.sleep(poll_interval)
        raise TimeoutError(f"Render timed out after {timeout}s")
