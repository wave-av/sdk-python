"""WAVE SDK - Chapters API. Auto-generate and manage video chapters.

A video's chapters live under ``/v1/videos/{videoId}/chapters``: :meth:`ChaptersAPI.list_chapters`,
:meth:`ChaptersAPI.create_chapter` and :meth:`ChaptersAPI.detect`. The API publishes no operation
for polling a detection job; read the result with :meth:`ChaptersAPI.list_chapters`.
"""
from __future__ import annotations

import time
import warnings
from typing import Any

from pydantic import BaseModel

from wave_sdk.client import WaveClient, path_segment


def _video_path(video_id: str) -> str:
    # The video id is one path segment; encode anything that could leave it.
    return f"/v1/videos/{path_segment(video_id)}/chapters"


class Chapter(BaseModel):
    id: str; title: str; start_time: float; end_time: float; thumbnail_url: str | None = None; description: str | None = None

class ChapterSet(BaseModel):
    id: str; asset_id: str; status: str; chapters: list[Chapter] | None = None; created_at: str; updated_at: str

class ChaptersAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/chapters"
    def generate(self, asset_id: str, **kwargs: Any) -> ChapterSet: return ChapterSet(**self._client.post(self._base, json={"asset_id": asset_id, **kwargs}))
    def create_set(self, asset_id: str, name: str = "Custom", **kwargs: Any) -> ChapterSet: return ChapterSet(**self._client.post(f"{self._base}/sets", json={"asset_id": asset_id, "name": name, **kwargs}))
    def get_set(self, set_id: str) -> ChapterSet: return ChapterSet(**self._client.get(f"{self._base}/{set_id}"))
    def list_sets(self, **params: Any) -> dict: return self._client.get(self._base, params={k: v for k, v in params.items() if v is not None})
    def update_set(self, set_id: str, **kwargs: Any) -> ChapterSet: return ChapterSet(**self._client.patch(f"{self._base}/{set_id}", json=kwargs))
    def remove_set(self, set_id: str) -> None: self._client.delete(f"{self._base}/{set_id}")
    def duplicate_set(self, set_id: str) -> ChapterSet: return ChapterSet(**self._client.post(f"{self._base}/{set_id}/duplicate"))
    # --- Per-video chapters: /v1/videos/{videoId}/chapters* -------------------------------------
    def list_chapters(self, video_id: str) -> dict[str, Any]:
        """A video's chapters. ``GET /v1/videos/{videoId}/chapters`` -> ``{"chapters": [...]}``."""
        result: dict[str, Any] = self._client.get(_video_path(video_id))
        return result
    def create_chapter(self, video_id: str, title: str, start_time: float, end_time: float, description: str | None = None) -> dict[str, Any]:
        """Add one chapter to a video. ``POST /v1/videos/{videoId}/chapters``."""
        body = {"title": title, "startTime": start_time, "endTime": end_time, "description": description}
        # Sent once: a retry after the API created the chapter would create a duplicate.
        result: dict[str, Any] = self._client.post(_video_path(video_id), json={k: v for k, v in body.items() if v is not None}, no_retry=True)
        return result
    def detect(self, video_id: str, min_duration: float | None = None, max_chapters: int | None = None, include_descriptions: bool | None = None, include_thumbnails: bool | None = None) -> dict[str, Any]:
        """Start AI chapter detection. ``POST /v1/videos/{videoId}/chapters/detect`` -> a detection job (HTTP 202)."""
        body = {"minDuration": min_duration, "maxChapters": max_chapters, "includeDescriptions": include_descriptions, "includeThumbnails": include_thumbnails}
        # Sent once (billed): a retry after the API accepted the job would start a second one.
        result: dict[str, Any] = self._client.post(f"{_video_path(video_id)}/detect", json={k: v for k, v in body.items() if v is not None}, no_retry=True)
        return result
    def get_default_set(self, asset_id: str) -> ChapterSet:
        """Deprecated: calls ``/v1/chapters/default/{id}``, which the API does not serve. Use :meth:`list_chapters`."""
        warnings.warn("chapters.get_default_set() calls a route the API does not serve; use chapters.list_chapters(video_id)", DeprecationWarning, stacklevel=2)
        return ChapterSet(**self._client.get(f"{self._base}/default/{asset_id}"))
    def add_chapter(self, set_id: str, title: str, start_time: float, end_time: float, **kwargs: Any) -> Chapter:
        """Deprecated: calls ``/v1/chapters/{set}/chapters``, which the API does not serve. Use :meth:`create_chapter`."""
        warnings.warn("chapters.add_chapter() calls a route the API does not serve; use chapters.create_chapter(video_id, ...)", DeprecationWarning, stacklevel=2)
        return Chapter(**self._client.post(f"{self._base}/{set_id}/chapters", json={"title": title, "start_time": start_time, "end_time": end_time, **kwargs}))
    def get_chapter(self, set_id: str, chapter_id: str) -> Chapter: return Chapter(**self._client.get(f"{self._base}/{set_id}/chapters/{chapter_id}"))
    def update_chapter(self, set_id: str, chapter_id: str, **kwargs: Any) -> Chapter: return Chapter(**self._client.patch(f"{self._base}/{set_id}/chapters/{chapter_id}", json=kwargs))
    def remove_chapter(self, set_id: str, chapter_id: str) -> None: self._client.delete(f"{self._base}/{set_id}/chapters/{chapter_id}")
    def get_chapter_at_time(self, set_id: str, time_seconds: float) -> Chapter: return Chapter(**self._client.get(f"{self._base}/{set_id}/at-time", params={"time": time_seconds}))
    def reorder_chapters(self, set_id: str, chapter_ids: list[str]) -> list[Chapter]: return [Chapter(**c) for c in self._client.put(f"{self._base}/{set_id}/reorder", json={"chapter_ids": chapter_ids})]
    def split_chapter(self, set_id: str, chapter_id: str, split_time: float) -> list[Chapter]: return [Chapter(**c) for c in self._client.post(f"{self._base}/{set_id}/chapters/{chapter_id}/split", json={"split_time": split_time})]
    def merge_chapters(self, set_id: str, chapter_ids: list[str]) -> Chapter: return Chapter(**self._client.post(f"{self._base}/{set_id}/merge", json={"chapter_ids": chapter_ids}))
    def bulk_update_chapters(self, set_id: str, chapters: list[dict]) -> list[Chapter]: return [Chapter(**c) for c in self._client.put(f"{self._base}/{set_id}/chapters", json={"chapters": chapters})]
    def generate_thumbnail(self, set_id: str, chapter_id: str) -> Chapter: return Chapter(**self._client.post(f"{self._base}/{set_id}/chapters/{chapter_id}/thumbnail"))
    def generate_all_thumbnails(self, set_id: str) -> ChapterSet: return ChapterSet(**self._client.post(f"{self._base}/{set_id}/thumbnails"))
    def export_chapters(self, set_id: str, format: str = "json") -> dict: return self._client.get(f"{self._base}/{set_id}/export", params={"format": format})
    def import_chapters(self, asset_id: str, format: str, content: str) -> ChapterSet: return ChapterSet(**self._client.post(f"{self._base}/import", json={"asset_id": asset_id, "format": format, "content": content}))
    def wait_for_ready(self, set_id: str, poll_interval: float = 2.0, timeout: float = 300.0) -> ChapterSet:
        start = time.time()
        while time.time() - start < timeout:
            s = self.get_set(set_id)
            if s.status == "ready": return s
            if s.status == "failed": raise RuntimeError("Chapter generation failed")
            time.sleep(poll_interval)
        raise TimeoutError(f"Chapters timed out after {timeout}s")
