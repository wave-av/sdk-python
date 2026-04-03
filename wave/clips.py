"""
WAVE SDK - Clips API

Create, manage, and export video clips from streams and recordings.
"""

from __future__ import annotations

import time
from typing import Any, Literal
from pydantic import BaseModel

from wave.client import WaveClient


class ClipSource(BaseModel):
    """Clip source reference."""

    type: Literal["stream", "recording", "upload"]
    id: str
    start_time: float
    end_time: float


class Clip(BaseModel):
    """Clip object."""

    id: str
    organization_id: str
    title: str
    description: str | None = None
    source: ClipSource
    status: Literal["pending", "processing", "ready", "failed", "deleted"]
    duration: float
    thumbnail_url: str | None = None
    playback_url: str | None = None
    download_url: str | None = None
    file_size: int | None = None
    width: int | None = None
    height: int | None = None
    frame_rate: float | None = None
    bitrate: int | None = None
    codec: str | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None
    error: str | None = None
    created_at: str
    updated_at: str


class ClipExport(BaseModel):
    """Export job status."""

    id: str
    clip_id: str
    status: Literal["pending", "processing", "ready", "failed"]
    format: str
    download_url: str | None = None
    file_size: int | None = None
    expires_at: str | None = None
    error: str | None = None
    created_at: str
    updated_at: str


class ClipHighlight(BaseModel):
    """Auto-highlight result."""

    start_time: float
    end_time: float
    score: float
    type: Literal["action", "speech", "emotion", "custom"]
    label: str | None = None


class ClipsAPI:
    """
    Clips API client.

    Example:
        >>> from wave import Wave
        >>> wave = Wave(api_key="your-api-key")
        >>> clip = wave.clips.create(
        ...     title="Best Moment",
        ...     source={"type": "stream", "id": "stream_123", "start_time": 120, "end_time": 150}
        ... )
        >>> ready = wave.clips.wait_for_ready(clip.id)
    """

    def __init__(self, client: WaveClient):
        self._client = client
        self._base_path = "/v1/clips"

    def create(
        self,
        title: str,
        source: dict[str, Any] | ClipSource,
        description: str | None = None,
        quality: str | None = None,
        format: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        auto_highlights: bool | None = None,
        webhook_url: str | None = None,
    ) -> Clip:
        """
        Create a new clip.

        Args:
            title: Clip title
            source: Source reference with type, id, start_time, end_time
            description: Optional description
            quality: Quality preset (low, medium, high, source)
            format: Export format (mp4, webm, mov, gif)
            tags: Optional tags
            metadata: Custom metadata
            auto_highlights: Enable AI highlight detection
            webhook_url: Webhook URL for status updates

        Returns:
            Created clip object
        """
        data: dict[str, Any] = {"title": title, "source": source}
        if description is not None:
            data["description"] = description
        if quality is not None:
            data["quality"] = quality
        if format is not None:
            data["format"] = format
        if tags is not None:
            data["tags"] = tags
        if metadata is not None:
            data["metadata"] = metadata
        if auto_highlights is not None:
            data["auto_highlights"] = auto_highlights
        if webhook_url is not None:
            data["webhook_url"] = webhook_url

        response = self._client.post(self._base_path, json=data)
        return Clip(**response)

    def get(self, clip_id: str) -> Clip:
        """Get a clip by ID."""
        response = self._client.get(f"{self._base_path}/{clip_id}")
        return Clip(**response)

    def update(
        self,
        clip_id: str,
        title: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Clip:
        """Update a clip."""
        data: dict[str, Any] = {}
        if title is not None:
            data["title"] = title
        if description is not None:
            data["description"] = description
        if tags is not None:
            data["tags"] = tags
        if metadata is not None:
            data["metadata"] = metadata

        response = self._client.patch(f"{self._base_path}/{clip_id}", json=data)
        return Clip(**response)

    def remove(self, clip_id: str) -> None:
        """Remove a clip."""
        self._client.delete(f"{self._base_path}/{clip_id}")

    def list(
        self,
        status: str | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        tags: list[str] | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
        order_by: str | None = None,
        order: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List clips with optional filters."""
        params: dict[str, Any] = {}
        if status is not None:
            params["status"] = status
        if source_type is not None:
            params["source_type"] = source_type
        if source_id is not None:
            params["source_id"] = source_id
        if tags is not None:
            params["tags"] = ",".join(tags)
        if created_after is not None:
            params["created_after"] = created_after
        if created_before is not None:
            params["created_before"] = created_before
        if order_by is not None:
            params["order_by"] = order_by
        if order is not None:
            params["order"] = order
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        return self._client.get(self._base_path, params=params)

    def export_clip(
        self,
        clip_id: str,
        format: str,
        quality: str | None = None,
        resolution: str | None = None,
        bitrate: int | None = None,
        include_audio: bool | None = None,
        watermark: dict[str, Any] | None = None,
    ) -> ClipExport:
        """Export a clip to a different format."""
        data: dict[str, Any] = {"format": format}
        if quality is not None:
            data["quality"] = quality
        if resolution is not None:
            data["resolution"] = resolution
        if bitrate is not None:
            data["bitrate"] = bitrate
        if include_audio is not None:
            data["include_audio"] = include_audio
        if watermark is not None:
            data["watermark"] = watermark

        response = self._client.post(f"{self._base_path}/{clip_id}/export", json=data)
        return ClipExport(**response)

    def get_export(self, clip_id: str, export_id: str) -> ClipExport:
        """Get export job status."""
        response = self._client.get(f"{self._base_path}/{clip_id}/exports/{export_id}")
        return ClipExport(**response)

    def list_exports(
        self,
        clip_id: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List all exports for a clip."""
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        return self._client.get(f"{self._base_path}/{clip_id}/exports", params=params)

    def detect_highlights(
        self,
        source_type: Literal["stream", "recording"],
        source_id: str,
        types: list[str] | None = None,
        min_score: float | None = None,
        max_results: int | None = None,
    ) -> list[ClipHighlight]:
        """Detect highlights in source content."""
        data: dict[str, Any] = {
            "source_type": source_type,
            "source_id": source_id,
        }
        if types is not None:
            data["types"] = types
        if min_score is not None:
            data["min_score"] = min_score
        if max_results is not None:
            data["max_results"] = max_results

        response = self._client.post(f"{self._base_path}/highlights/detect", json=data)
        return [ClipHighlight(**h) for h in response]

    def create_from_highlights(
        self,
        source_type: Literal["stream", "recording"],
        source_id: str,
        min_score: float | None = None,
        max_clips: int | None = None,
        title_prefix: str | None = None,
        tags: list[str] | None = None,
    ) -> list[Clip]:
        """Generate clips from detected highlights."""
        data: dict[str, Any] = {
            "source_type": source_type,
            "source_id": source_id,
        }
        if min_score is not None:
            data["min_score"] = min_score
        if max_clips is not None:
            data["max_clips"] = max_clips
        if title_prefix is not None:
            data["title_prefix"] = title_prefix
        if tags is not None:
            data["tags"] = tags

        response = self._client.post(f"{self._base_path}/highlights/create", json=data)
        return [Clip(**c) for c in response]

    def wait_for_ready(
        self,
        clip_id: str,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
        on_progress: callable | None = None,
    ) -> Clip:
        """
        Wait for a clip to be ready.

        Args:
            clip_id: Clip ID to wait for
            poll_interval: Polling interval in seconds
            timeout: Maximum wait time in seconds
            on_progress: Optional callback for progress updates

        Returns:
            Ready clip object

        Raises:
            TimeoutError: If clip doesn't complete within timeout
            RuntimeError: If clip processing fails
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            clip = self.get(clip_id)

            if on_progress:
                on_progress(clip)

            if clip.status == "ready":
                return clip

            if clip.status == "failed":
                raise RuntimeError(f"Clip processing failed: {clip.error or 'Unknown error'}")

            time.sleep(poll_interval)

        raise TimeoutError(f"Clip processing timed out after {timeout}s")

    def wait_for_export(
        self,
        clip_id: str,
        export_id: str,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> ClipExport:
        """Wait for an export to be ready."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            export = self.get_export(clip_id, export_id)

            if export.status == "ready":
                return export

            if export.status == "failed":
                raise RuntimeError(f"Export failed: {export.error or 'Unknown error'}")

            time.sleep(poll_interval)

        raise TimeoutError(f"Export timed out after {timeout}s")
