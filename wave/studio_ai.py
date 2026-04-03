"""WAVE SDK - Studio AI API. AI-powered production assistance, directing, and moderation."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from wave.client import WaveClient

class AIAssistant(BaseModel):
    id: str; production_id: str | None = None; stream_id: str | None = None; mode: str; status: str; config: dict | None = None; stats: dict | None = None; started_at: str | None = None; created_at: str; updated_at: str

class AISuggestion(BaseModel):
    id: str; assistant_id: str; type: str; confidence: float; description: str; action: dict | None = None; status: str; priority: str = "normal"; created_at: str

class StudioAIAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/studio-ai"
    def start_assistant(self, stream_id: str, mode: str = "assisted", **kwargs: Any) -> AIAssistant: return AIAssistant(**self._client.post(f"{self._base}/assistants", json={"stream_id": stream_id, "mode": mode, **kwargs}))
    def get_assistant(self, assistant_id: str) -> AIAssistant: return AIAssistant(**self._client.get(f"{self._base}/assistants/{assistant_id}"))
    def update_assistant(self, assistant_id: str, **kwargs: Any) -> AIAssistant: return AIAssistant(**self._client.patch(f"{self._base}/assistants/{assistant_id}", json=kwargs))
    def stop_assistant(self, assistant_id: str) -> None: self._client.post(f"{self._base}/assistants/{assistant_id}/stop")
    def pause_assistant(self, assistant_id: str) -> None: self._client.post(f"{self._base}/assistants/{assistant_id}/pause")
    def resume_assistant(self, assistant_id: str) -> None: self._client.post(f"{self._base}/assistants/{assistant_id}/resume")
    def list_assistants(self, **params: Any) -> dict: return self._client.get(f"{self._base}/assistants", params={k: v for k, v in params.items() if v is not None})
    def get_assistant_stats(self, assistant_id: str) -> dict: return self._client.get(f"{self._base}/assistants/{assistant_id}/stats")
    def set_director_rules(self, assistant_id: str, rules: list[dict]) -> dict: return self._client.put(f"{self._base}/assistants/{assistant_id}/rules", json={"rules": rules})
    def list_suggestions(self, assistant_id: str, **params: Any) -> dict: return self._client.get(f"{self._base}/assistants/{assistant_id}/suggestions", params={k: v for k, v in params.items() if v is not None})
    def get_suggestion(self, suggestion_id: str) -> AISuggestion: return AISuggestion(**self._client.get(f"{self._base}/suggestions/{suggestion_id}"))
    def accept_suggestion(self, suggestion_id: str) -> AISuggestion: return AISuggestion(**self._client.post(f"{self._base}/suggestions/{suggestion_id}/accept"))
    def reject_suggestion(self, suggestion_id: str) -> AISuggestion: return AISuggestion(**self._client.post(f"{self._base}/suggestions/{suggestion_id}/reject"))
    def apply_suggestion(self, suggestion_id: str) -> AISuggestion: return AISuggestion(**self._client.post(f"{self._base}/suggestions/{suggestion_id}/apply"))
    def dismiss_alert(self, alert_id: str) -> None: self._client.post(f"{self._base}/alerts/{alert_id}/dismiss")
    def get_scene_recommendations(self, assistant_id: str) -> list[dict]: return self._client.get(f"{self._base}/assistants/{assistant_id}/scene-recommendations")
    def get_graphics_suggestions(self, assistant_id: str) -> list[dict]: return self._client.get(f"{self._base}/assistants/{assistant_id}/graphics-suggestions")
    def get_audio_suggestions(self, assistant_id: str) -> list[dict]: return self._client.get(f"{self._base}/assistants/{assistant_id}/audio-suggestions")
    def get_moderation_alerts(self, assistant_id: str) -> list[dict]: return self._client.get(f"{self._base}/assistants/{assistant_id}/moderation-alerts")
    def set_moderation_sensitivity(self, assistant_id: str, level: str) -> dict: return self._client.patch(f"{self._base}/assistants/{assistant_id}/moderation", json={"sensitivity": level})
    def get_engagement_insights(self, assistant_id: str) -> list[dict]: return self._client.get(f"{self._base}/assistants/{assistant_id}/engagement-insights")
    def suggest_scene_switch(self, assistant_id: str, source_id: str, reason: str | None = None) -> dict: return self._client.post(f"{self._base}/assistants/{assistant_id}/suggest-switch", json={"source_id": source_id, "reason": reason})
    def generate_lower_third(self, assistant_id: str, **kwargs: Any) -> dict: return self._client.post(f"{self._base}/assistants/{assistant_id}/generate-lower-third", json=kwargs if kwargs else None)
    def auto_level_audio(self, assistant_id: str) -> dict: return self._client.post(f"{self._base}/assistants/{assistant_id}/auto-level-audio")
    def get_optimal_interaction_times(self, assistant_id: str) -> list[dict]: return self._client.get(f"{self._base}/assistants/{assistant_id}/interaction-times")
    def generate_engagement_action(self, assistant_id: str) -> dict: return self._client.post(f"{self._base}/assistants/{assistant_id}/engagement-action")
