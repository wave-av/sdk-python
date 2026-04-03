"""WAVE SDK - Sentiment API. Audience sentiment, emotion, and topic analysis."""
from __future__ import annotations
import time
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class SentimentAnalysis(BaseModel):
    id: str; asset_id: str; status: str; overall_sentiment: str | None = None; overall_score: float = 0; segments_count: int = 0; created_at: str; updated_at: str

class SentimentAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/sentiment"
    def analyze(self, asset_id: str, **kwargs: Any) -> SentimentAnalysis: return SentimentAnalysis(**self._client.post(self._base, json={"asset_id": asset_id, **kwargs}))
    def analyze_text(self, text: str, **kwargs: Any) -> dict: return self._client.post(f"{self._base}/text", json={"text": text, **kwargs})
    def get(self, analysis_id: str) -> SentimentAnalysis: return SentimentAnalysis(**self._client.get(f"{self._base}/{analysis_id}"))
    def list(self, **params: Any) -> dict: return self._client.get(self._base, params={k: v for k, v in params.items() if v is not None})
    def remove(self, analysis_id: str) -> None: self._client.delete(f"{self._base}/{analysis_id}")
    def get_segments(self, analysis_id: str) -> list[dict]: return self._client.get(f"{self._base}/{analysis_id}/segments")
    def get_summary(self, analysis_id: str) -> dict: return self._client.get(f"{self._base}/{analysis_id}/summary")
    def get_trend(self, analysis_id: str) -> dict: return self._client.get(f"{self._base}/{analysis_id}/trend")
    def get_key_moments(self, analysis_id: str) -> list[dict]: return self._client.get(f"{self._base}/{analysis_id}/key-moments")
    def get_topic_sentiments(self, analysis_id: str) -> list[dict]: return self._client.get(f"{self._base}/{analysis_id}/topics")
    def get_speaker_sentiment(self, analysis_id: str) -> list[dict]: return self._client.get(f"{self._base}/{analysis_id}/speakers")
    def compare(self, analysis_ids: list[str]) -> dict: return self._client.post(f"{self._base}/compare", json={"analysis_ids": analysis_ids})
    def export_analysis(self, analysis_id: str, format: str = "json") -> dict: return self._client.get(f"{self._base}/{analysis_id}/export", params={"format": format})
    def batch_analyze(self, asset_ids: list[str], **kwargs: Any) -> list[SentimentAnalysis]: return [SentimentAnalysis(**a) for a in self._client.post(f"{self._base}/batch", json={"asset_ids": asset_ids, **kwargs})]
    def get_supported_languages(self) -> list[dict]: return self._client.get(f"{self._base}/languages")
    def start_realtime(self, stream_id: str, **kwargs: Any) -> dict: return self._client.post(f"{self._base}/realtime/start", json={"stream_id": stream_id, **kwargs})
    def stop_realtime(self, stream_id: str) -> dict: return self._client.post(f"{self._base}/realtime/stop", json={"stream_id": stream_id})
    def get_realtime_status(self, stream_id: str) -> dict: return self._client.get(f"{self._base}/realtime/{stream_id}")
    def wait_for_ready(self, analysis_id: str, poll_interval: float = 3.0, timeout: float = 600.0) -> SentimentAnalysis:
        start = time.time()
        while time.time() - start < timeout:
            a = self.get(analysis_id)
            if a.status == "ready": return a
            if a.status == "failed": raise RuntimeError("Sentiment analysis failed")
            time.sleep(poll_interval)
        raise TimeoutError(f"Analysis timed out after {timeout}s")
