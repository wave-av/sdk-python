"""WAVE SDK - Transcript API. Read-only access to the voice-agent transcript
persisted to storage by the realtime plane (system + alternating user/assistant
turns), reached over the gateway's `/v1/realtime/agents/transcripts` surface."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from wave_sdk.client import WaveClient


class TranscriptMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: Any


class Transcript(BaseModel):
    org: str; room_id: str; session_id: str; recorded_at: int; messages: list[TranscriptMessage]


class TranscriptList(BaseModel):
    org: str; count: int; transcripts: list[str]


class TranscriptAPI:
    """The voice-agent transcript client. Read-only; lists and reads the retained
    transcripts for an org over the same `transcripts/*` surface the browser uses."""

    def __init__(self, client: WaveClient):
        self._client = client
        self._base = "/v1/realtime/agents/transcripts"

    def list(self, org: str) -> TranscriptList:
        """List the transcript object keys recorded for an org."""
        return TranscriptList(**self._client.get(f"{self._base}/{org}"))

    def get(self, org: str, room: str, session: str) -> Transcript:
        """Read one session's transcript."""
        return Transcript(**self._client.get(f"{self._base}/{org}/{room}/{session}"))
