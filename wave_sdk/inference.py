"""WAVE SDK - Inference API. One OpenAI-compatible completion endpoint fronting the WAVE model
registry: measured routing, automatic failover, per-token metering.

Both calls go through the API gateway with your WAVE API key, like every other namespace:

* ``complete()`` -> ``POST /v1/inference/chat/completions`` (scope ``dispatch:write``);
* ``models()``   -> ``GET /v1/inference/models`` (an OpenAI-style model list).

``profile()`` reads the model registry directly and needs the registry's own endpoint and key
(``registry_url`` / ``registry_key``); the WAVE API key is not a registry credential. It is
deprecated and will be removed in a future major release.
"""
from __future__ import annotations

import warnings
from typing import Any, Literal
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict

from wave_sdk.client import WaveClient, WaveError

_COMPLETIONS_PATH = "/v1/inference/chat/completions"
_MODELS_PATH = "/v1/inference/models"


class InferenceMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class InferenceResult(BaseModel):
    model: str
    content: str
    cost: float | None
    total_tokens: int


class InferenceModel(BaseModel):
    """One entry of ``GET /v1/inference/models``. ``rail`` and the per-token prices are only filled
    by the deprecated registry read; the gateway list carries ``id``, ``object`` and ``owned_by``."""

    model_config = ConfigDict(extra="allow")
    id: str
    object: str | None = None
    owned_by: str | None = None
    rail: str | None = None
    input_per_m: float | None = None
    output_per_m: float | None = None


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
    """Inference API - one completion call through the gateway, plus the model list.

    ``funnel_url`` is deprecated and ignored. It used to send completions, with the WAVE API key,
    straight to a proxy that does not accept WAVE API keys. Every completion now goes through the
    client's own host (``https://api.wave.online`` by default), so the key is never sent anywhere
    else.
    """

    def __init__(self, client: WaveClient, funnel_url: str | None = None, registry_url: str | None = None, registry_key: str | None = None):
        self._client = client
        if funnel_url is not None:
            warnings.warn(
                "InferenceAPI(funnel_url=...) is deprecated and ignored: completions go through the "
                f"API gateway ({_COMPLETIONS_PATH}), which accepts your WAVE API key.",
                DeprecationWarning,
                stacklevel=2,
            )
        self._registry_url = (registry_url or "").rstrip("/")
        self._registry_key = registry_key or ""

    def complete(self, model: str, messages: list[InferenceMessage | dict[str, Any]], max_tokens: int = 1024) -> InferenceResult:
        """One completion. ``POST /v1/inference/chat/completions``; raises WaveError on HTTP errors."""
        msgs = [m.model_dump() if isinstance(m, InferenceMessage) else m for m in messages]
        body = {"model": model, "messages": msgs, "max_tokens": max_tokens}
        data = self._client.post(_COMPLETIONS_PATH, json=body, timeout=120.0)
        data = data if isinstance(data, dict) else {}
        usage = data.get("usage") or {}
        choices = data.get("choices") or [{}]
        return InferenceResult(
            model=data.get("model") or model,
            content=(choices[0].get("message") or {}).get("content") or "",
            cost=usage.get("cost"),
            total_tokens=usage.get("total_tokens") or 0,
        )

    def models(self) -> list[InferenceModel]:
        """Models the gateway will dispatch to. ``GET /v1/inference/models``."""
        data = self._client.get(_MODELS_PATH)
        rows = data.get("data") if isinstance(data, dict) else data
        return [InferenceModel(**r) for r in (rows or []) if isinstance(r, dict)]

    def profile(self, model_id: str) -> ModelProfile:
        """Deprecated. A model's measured profile read straight from the registry; requires
        ``registry_url`` and ``registry_key``."""
        warnings.warn(
            "InferenceAPI.profile() reads the model registry directly and is deprecated; "
            "use models() for the gateway's model list.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Encoded so a model id cannot add filters of its own to the registry query.
        mid = quote(model_id, safe="")
        rows = self._registry_get(f"/rest/v1/models?select=*&id=eq.{mid}")
        if not rows:
            raise WaveError(f"model {model_id}: NOT ADMITTED", "MODEL_NOT_FOUND", 404)
        row = rows[0]
        health = row.get("health") or {}
        usage = self._registry_get(f"/rest/v1/usage_logs?select=cost,latency_ms&model_id=eq.{mid}&limit=1000")
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
            raise WaveError("InferenceAPI: registry_url is required for profile()", "REGISTRY_UNCONFIGURED", 0)
        response = httpx.get(f"{self._registry_url}{path}", headers={"apikey": self._registry_key}, timeout=20.0)
        if not response.is_success:
            raise WaveError(f"registry {response.status_code}: {response.text[:200]}", "REGISTRY_ERROR", response.status_code)
        data: list[dict[str, Any]] = response.json()
        return data
