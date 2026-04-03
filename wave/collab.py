"""WAVE SDK - Collab API. Real-time collaboration rooms, participants, comments, and annotations."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class CollabRoom(BaseModel):
    id: str; organization_id: str; name: str; status: str; participant_count: int = 0; max_participants: int = 50; settings: dict | None = None; created_at: str; updated_at: str

class Participant(BaseModel):
    id: str; user_id: str; name: str; role: str; status: str; permissions: dict | None = None; joined_at: str

class Comment(BaseModel):
    id: str; room_id: str; user_id: str; text: str; timestamp: float | None = None; parent_id: str | None = None; reactions: list[dict] | None = None; created_at: str; updated_at: str

class Annotation(BaseModel):
    id: str; room_id: str; user_id: str; type: str; data: dict; timestamp: float | None = None; created_at: str

class CollabAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/collab"
    def create_room(self, name: str, **kwargs: Any) -> CollabRoom: return CollabRoom(**self._client.post(f"{self._base}/rooms", json={"name": name, **kwargs}))
    def get_room(self, room_id: str) -> CollabRoom: return CollabRoom(**self._client.get(f"{self._base}/rooms/{room_id}"))
    def update_room(self, room_id: str, **kwargs: Any) -> CollabRoom: return CollabRoom(**self._client.patch(f"{self._base}/rooms/{room_id}", json=kwargs))
    def list_rooms(self, **params: Any) -> dict: return self._client.get(f"{self._base}/rooms", params={k: v for k, v in params.items() if v is not None})
    def close_room(self, room_id: str) -> None: self._client.post(f"{self._base}/rooms/{room_id}/close")
    def archive_room(self, room_id: str) -> None: self._client.post(f"{self._base}/rooms/{room_id}/archive")
    def get_join_token(self, room_id: str) -> dict: return self._client.post(f"{self._base}/rooms/{room_id}/join-token")
    def invite(self, room_id: str, user_ids: list[str], role: str = "viewer") -> None: self._client.post(f"{self._base}/rooms/{room_id}/invite", json={"user_ids": user_ids, "role": role})
    def list_participants(self, room_id: str) -> list[Participant]: return [Participant(**p) for p in self._client.get(f"{self._base}/rooms/{room_id}/participants")]
    def get_participant(self, room_id: str, participant_id: str) -> Participant: return Participant(**self._client.get(f"{self._base}/rooms/{room_id}/participants/{participant_id}"))
    def update_participant(self, room_id: str, participant_id: str, **kwargs: Any) -> Participant: return Participant(**self._client.patch(f"{self._base}/rooms/{room_id}/participants/{participant_id}", json=kwargs))
    def remove_participant(self, room_id: str, participant_id: str) -> None: self._client.delete(f"{self._base}/rooms/{room_id}/participants/{participant_id}")
    def list_comments(self, room_id: str, **params: Any) -> list[Comment]: return [Comment(**c) for c in self._client.get(f"{self._base}/rooms/{room_id}/comments", params={k: v for k, v in params.items() if v is not None})]
    def add_comment(self, room_id: str, text: str, **kwargs: Any) -> Comment: return Comment(**self._client.post(f"{self._base}/rooms/{room_id}/comments", json={"text": text, **kwargs}))
    def update_comment(self, room_id: str, comment_id: str, text: str) -> Comment: return Comment(**self._client.patch(f"{self._base}/rooms/{room_id}/comments/{comment_id}", json={"text": text}))
    def remove_comment(self, room_id: str, comment_id: str) -> None: self._client.delete(f"{self._base}/rooms/{room_id}/comments/{comment_id}")
    def add_reaction(self, room_id: str, comment_id: str, emoji: str) -> None: self._client.post(f"{self._base}/rooms/{room_id}/comments/{comment_id}/reactions", json={"emoji": emoji})
    def remove_reaction(self, room_id: str, comment_id: str, reaction_id: str) -> None: self._client.delete(f"{self._base}/rooms/{room_id}/comments/{comment_id}/reactions/{reaction_id}")
    def list_annotations(self, room_id: str) -> list[Annotation]: return [Annotation(**a) for a in self._client.get(f"{self._base}/rooms/{room_id}/annotations")]
    def add_annotation(self, room_id: str, type: str, data: dict, **kwargs: Any) -> Annotation: return Annotation(**self._client.post(f"{self._base}/rooms/{room_id}/annotations", json={"type": type, "data": data, **kwargs}))
    def update_annotation(self, room_id: str, annotation_id: str, **kwargs: Any) -> Annotation: return Annotation(**self._client.patch(f"{self._base}/rooms/{room_id}/annotations/{annotation_id}", json=kwargs))
    def remove_annotation(self, room_id: str, annotation_id: str) -> None: self._client.delete(f"{self._base}/rooms/{room_id}/annotations/{annotation_id}")
    def clear_annotations(self, room_id: str) -> None: self._client.delete(f"{self._base}/rooms/{room_id}/annotations")
    def start_recording(self, room_id: str) -> dict: return self._client.post(f"{self._base}/rooms/{room_id}/recording/start")
    def stop_recording(self, room_id: str) -> dict: return self._client.post(f"{self._base}/rooms/{room_id}/recording/stop")
    def get_recording_status(self, room_id: str) -> dict: return self._client.get(f"{self._base}/rooms/{room_id}/recording")
