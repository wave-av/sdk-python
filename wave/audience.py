"""WAVE SDK - Audience API. Polls, Q&A, reactions, and engagement."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class Poll(BaseModel):
    id: str; stream_id: str; question: str; options: list[dict]; status: str; total_votes: int = 0; created_at: str; updated_at: str

class QASession(BaseModel):
    id: str; stream_id: str; status: str; questions: list[dict] | None = None; created_at: str

class AudienceAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/audience"
    def create_poll(self, stream_id: str, question: str, options: list[str], **kwargs: Any) -> Poll: return Poll(**self._client.post(f"{self._base}/polls", json={"stream_id": stream_id, "question": question, "options": options, **kwargs}))
    def get_poll(self, poll_id: str) -> Poll: return Poll(**self._client.get(f"{self._base}/polls/{poll_id}"))
    def close_poll(self, poll_id: str) -> Poll: return Poll(**self._client.post(f"{self._base}/polls/{poll_id}/close"))
    def vote(self, poll_id: str, option_ids: list[str]) -> None: self._client.post(f"{self._base}/polls/{poll_id}/vote", json={"option_ids": option_ids})
    def create_qa(self, stream_id: str, **kwargs: Any) -> QASession: return QASession(**self._client.post(f"{self._base}/qa", json={"stream_id": stream_id, **kwargs}))
    def get_qa(self, session_id: str) -> QASession: return QASession(**self._client.get(f"{self._base}/qa/{session_id}"))
    def close_qa(self, session_id: str) -> None: self._client.post(f"{self._base}/qa/{session_id}/close")
    def submit_question(self, session_id: str, text: str) -> dict: return self._client.post(f"{self._base}/qa/{session_id}/questions", json={"text": text})
    def answer_question(self, session_id: str, question_id: str, answer: str) -> dict: return self._client.post(f"{self._base}/qa/{session_id}/questions/{question_id}/answer", json={"answer": answer})
    def send_reaction(self, stream_id: str, type: str) -> None: self._client.post(f"{self._base}/reactions", json={"stream_id": stream_id, "type": type})
    def get_engagement_metrics(self, stream_id: str) -> dict: return self._client.get(f"{self._base}/engagement/{stream_id}")
