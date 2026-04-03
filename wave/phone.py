"""WAVE SDK - Phone API. Voice calls, conferences, numbers, and recordings."""
from __future__ import annotations
import time
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class PhoneNumber(BaseModel):
    id: str; number: str; type: str; capabilities: list[str] | None = None; status: str; region: str | None = None; created_at: str; updated_at: str

class Call(BaseModel):
    id: str; from_number: str; to_number: str; status: str; direction: str; duration: float | None = None; recording_url: str | None = None; created_at: str

class Conference(BaseModel):
    id: str; name: str; status: str; participant_count: int = 0; max_participants: int = 100; created_at: str

class ConferenceParticipant(BaseModel):
    id: str; call_id: str; status: str; muted: bool = False; hold: bool = False; joined_at: str

class PhoneAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/phone"
    def list_numbers(self, **params: Any) -> dict: return self._client.get(f"{self._base}/numbers", params={k: v for k, v in params.items() if v is not None})
    def get_number(self, number_id: str) -> PhoneNumber: return PhoneNumber(**self._client.get(f"{self._base}/numbers/{number_id}"))
    def purchase_number(self, number: str, **kwargs: Any) -> PhoneNumber: return PhoneNumber(**self._client.post(f"{self._base}/numbers", json={"number": number, **kwargs}))
    def update_number(self, number_id: str, **kwargs: Any) -> PhoneNumber: return PhoneNumber(**self._client.patch(f"{self._base}/numbers/{number_id}", json=kwargs))
    def release_number(self, number_id: str) -> None: self._client.delete(f"{self._base}/numbers/{number_id}")
    def search_available_numbers(self, country: str = "US", **params: Any) -> list[dict]: return self._client.get(f"{self._base}/numbers/available", params={"country": country, **{k: v for k, v in params.items() if v is not None}})
    def validate_number(self, number: str) -> dict: return self._client.post(f"{self._base}/numbers/validate", json={"number": number})
    def get_supported_countries(self) -> list[dict]: return self._client.get(f"{self._base}/numbers/countries")
    def make_call(self, from_number: str, to_number: str, **kwargs: Any) -> Call: return Call(**self._client.post(f"{self._base}/calls", json={"from": from_number, "to": to_number, **kwargs}))
    def get_call(self, call_id: str) -> Call: return Call(**self._client.get(f"{self._base}/calls/{call_id}"))
    def update_call(self, call_id: str, **kwargs: Any) -> Call: return Call(**self._client.patch(f"{self._base}/calls/{call_id}", json=kwargs))
    def end_call(self, call_id: str) -> None: self._client.post(f"{self._base}/calls/{call_id}/end")
    def list_calls(self, **params: Any) -> dict: return self._client.get(f"{self._base}/calls", params={k: v for k, v in params.items() if v is not None})
    def get_recording(self, call_id: str) -> dict: return self._client.get(f"{self._base}/calls/{call_id}/recording")
    def create_conference(self, name: str, **kwargs: Any) -> Conference: return Conference(**self._client.post(f"{self._base}/conferences", json={"name": name, **kwargs}))
    def get_conference(self, conference_id: str) -> Conference: return Conference(**self._client.get(f"{self._base}/conferences/{conference_id}"))
    def end_conference(self, conference_id: str) -> None: self._client.post(f"{self._base}/conferences/{conference_id}/end")
    def list_conferences(self, **params: Any) -> dict: return self._client.get(f"{self._base}/conferences", params={k: v for k, v in params.items() if v is not None})
    def add_conference_participant(self, conference_id: str, call_id: str) -> ConferenceParticipant: return ConferenceParticipant(**self._client.post(f"{self._base}/conferences/{conference_id}/participants", json={"call_id": call_id}))
    def update_conference_participant(self, conference_id: str, participant_id: str, **kwargs: Any) -> ConferenceParticipant: return ConferenceParticipant(**self._client.patch(f"{self._base}/conferences/{conference_id}/participants/{participant_id}", json=kwargs))
    def remove_conference_participant(self, conference_id: str, participant_id: str) -> None: self._client.delete(f"{self._base}/conferences/{conference_id}/participants/{participant_id}")
    def wait_for_call_end(self, call_id: str, poll_interval: float = 2.0, timeout: float = 3600.0) -> Call:
        start = time.time()
        while time.time() - start < timeout:
            c = self.get_call(call_id)
            if c.status in ("completed", "failed", "busy", "no-answer"): return c
            time.sleep(poll_interval)
        raise TimeoutError(f"Call did not end within {timeout}s")
