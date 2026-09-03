"""WAVE SDK - Inference API (the funnel rendering). One OpenAI-compatible
completion endpoint fronting the WAVE model registry - measured routing,
automatic failover, per-token metering. The SDK forwards the API key; auth,
budgets, guardrails, and spend tracking are enforced by the funnel plane
(inference.wave.online).

The routing decision is measured: every model carries a floor-to-ceiling
transition profile in the registry. `profile()` returns it alongside live
usage. Reading the registry directly (`models`, `profile`) requires the
caller to supply the registry's own read endpoint and key - the WAVE API key
alone is not a registry credential.
"""
from __future__ import annotations

from typing import Any, Literal
from wave.client import WaveClient, WaveError

import httpx
from pydantic import BaseModel


class InferenceMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class InferenceResult(BaseModel):
    model: str
    content: str
    cost: float | None
    total_tokens: int


class InferenceModel(BaseModel):
    id: str
    rail: str
    input_per_m: float | None
    output_per_m: float | None


class ModelTransition(BaseModel):
    floor: float | None
    ceiling: float | None


class ModelPricing(BaseModel):
    input_per_m: float | None
    output_per_m: float | None


class ModelLiveUsage(BaseModel):
    calls: int
    spent_usd: float
    avg_latency_ms: float | None


class ModelProfile(BaseModel):
    id: str
    rail: str
    status: str
    transition: ModelTransition
    pricing: ModelPricing
    live_usage: ModelLiveUsage


class InferenceAPI:
    """Inference API - one completion call through the measured funnel, plus
    registry reads (model catalog, measured profile)."""

    def __init__(self, client: WaveClient, funnel_url: str | None = None, registry_url: str | None = None, registry_key: str | None = None):
        self._client = client
        self._funnel_url = (funnel_url or "https://inference.wave.online").rstrip("/")
        self._registry_url = (registry_url or "").rstrip("/")
        self._registry_key = registry_key or ""

    def complete(self, model: str, messages: list[InferenceMessage | dict[str, Any]], max_tokens: int = 1024) -> InferenceResult:
        """One completion through the measured funnel. Raises WaveError on HTTP errors."""
        msgs = [m.model_dump() if isinstance(m, InferenceMessage) else m for m in messages]
        response = httpx.post(
            f"{self._funnel_url}/v1/chat/completions",
            headers={"content-type": "application/json", "authorization": f"Bearer {self._client.api_key}"},
            json={"model": model, "messages": msgs, "max_tokens": max_tokens},
            timeout=120.0,
        )
        if not response.is_success:
            raise WaveError(f"inference {response.status_code}: {response.text[:300]}", "INFERENCE_ERROR", response.status_code)
        data = response.json()
        usage = data.get("usage") or {}
        choices = data.get("choices") or [{}]
        return InferenceResult(
            model=data.get("model") or model,
            content=(choices[0].get("message") or {}).get("content") or "",
            cost=usage.get("cost"),
            total_tokens=usage.get("total_tokens") or 0,
        )

    def models(self) -> list[InferenceModel]:
        """Models admitted to the registry with their per-token pricing."""
        rows = self._registry_get("/rest/v1/models?select=id,rail,cost_input_per_m,cost_output_per_m&limit=1000")
        return [InferenceModel(id=r["id"], rail=r["rail"], input_per_m=r.get("cost_input_per_m"), output_per_m=r.get("cost_output_per_m")) for r in rows]

    def profile(self, model_id: str) -> ModelProfile:
        """A model's measured profile: the transition signature + pricing + live usage."""
        rows = self._registry_get(f"/rest/v1/models?select=*&id=eq.{model_id}")
        if not rows:
            raise WaveError(f"model {model_id}: NOT ADMITTED", "MODEL_NOT_FOUND", 404)
        row = rows[0]
        health = row.get("health") or {}
        usage = self._registry_get(f"/rest/v1/usage_logs?select=cost,latency_ms&model_id=eq.{model_id}&limit=1000")
        latencies = [float(u["latency_ms"]) for u in usage if u.get("latency_ms") is not None and float(u["latency_ms"]) > 0]
        return ModelProfile(
            id=row["id"],
            rail=row["rail"],
            status=row["status"],
            transition=ModelTransition(floor=health.get("floor"), ceiling=health.get("ceiling")),
            pricing=ModelPricing(input_per_m=row.get("cost_input_per_m"), output_per_m=row.get("cost_output_per_m")),
            live_usage=ModelLiveUsage(
                calls=len(usage),
                spent_usd=sum(float(u.get("cost") or 0) for u in usage),
                avg_latency_ms=(sum(latencies) / len(latencies)) if latencies else None,
            ),
        )

    def _registry_get(self, path: str) -> list[dict[str, Any]]:
        if not self._registry_url:
            raise WaveError("InferenceAPI: registry_url is required for models()/profile()", "REGISTRY_UNCONFIGURED", 0)
        response = httpx.get(f"{self._registry_url}{path}", headers={"apikey": self._registry_key}, timeout=20.0)
        if not response.is_success:
            raise WaveError(f"registry {response.status_code}: {response.text[:200]}", "REGISTRY_ERROR", response.status_code)
        data: list[dict[str, Any]] = response.json()
        return data
