"""WAVE SDK - Zoom API. Zoom meetings, rooms, recordings, and RTMS."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class ZoomMeeting(BaseModel):
    id: str; topic: str; type: str; status: str; start_url: str; join_url: str; host_id: str; duration_minutes: int; participants_count: int = 0; recording_enabled: bool = False; rtms_enabled: bool = False; created_at: str

class ZoomRoom(BaseModel):
    id: str; name: str; location: str | None = None; status: str; account_id: str; camera_count: int = 0; microphone_count: int = 0

class ZoomRecording(BaseModel):
    id: str; meeting_id: str; type: str; status: str; file_url: str | None = None; duration_seconds: int = 0; file_size_bytes: int = 0; created_at: str

class ZoomAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/zoom"
    def create_meeting(self, topic: str, **kwargs: Any) -> ZoomMeeting: return ZoomMeeting(**self._client.post(f"{self._base}/meetings", json={"topic": topic, **kwargs}))
    def get_meeting(self, meeting_id: str) -> ZoomMeeting: return ZoomMeeting(**self._client.get(f"{self._base}/meetings/{meeting_id}"))
    def end_meeting(self, meeting_id: str) -> None: self._client.post(f"{self._base}/meetings/{meeting_id}/end")
    def list_meetings(self, **params: Any) -> dict: return self._client.get(f"{self._base}/meetings", params={k: v for k, v in params.items() if v is not None})
    def list_rooms(self, **params: Any) -> dict: return self._client.get(f"{self._base}/rooms", params={k: v for k, v in params.items() if v is not None})
    def get_room_status(self, room_id: str) -> ZoomRoom: return ZoomRoom(**self._client.get(f"{self._base}/rooms/{room_id}"))
    def get_recording(self, recording_id: str) -> ZoomRecording: return ZoomRecording(**self._client.get(f"{self._base}/recordings/{recording_id}"))
    def list_recordings(self, meeting_id: str | None = None, **params: Any) -> dict: path = f"{self._base}/meetings/{meeting_id}/recordings" if meeting_id else f"{self._base}/recordings"; return self._client.get(path, params={k: v for k, v in params.items() if v is not None})
    def start_rtms(self, meeting_id: str, stream_url: str, stream_key: str) -> dict: return self._client.post(f"{self._base}/meetings/{meeting_id}/rtms/start", json={"stream_url": stream_url, "stream_key": stream_key})
    def stop_rtms(self, meeting_id: str) -> dict: return self._client.post(f"{self._base}/meetings/{meeting_id}/rtms/stop")
    def get_rtms_status(self, meeting_id: str) -> dict: return self._client.get(f"{self._base}/meetings/{meeting_id}/rtms")
