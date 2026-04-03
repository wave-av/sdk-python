"""WAVE Agent Framework for Python."""

from __future__ import annotations

from typing import Any, Callable, Optional
import httpx


class WaveAgent:
    """Base class for WAVE AI agents.

    Example:
        agent = WaveAgent(
            api_key="wave_sk_...",
            name="my-monitor",
            agent_type="stream_monitor",
        )
        await agent.start()
    """

    def __init__(
        self,
        api_key: str,
        name: str,
        agent_type: str = "custom",
        base_url: str = "https://api.wave.online",
    ) -> None:
        self.api_key = api_key
        self.name = name
        self.agent_type = agent_type
        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-Wave-Agent": name,
            },
        )
        self._handlers: dict[str, list[Callable[..., Any]]] = {}
        self._running = False

    def on(self, event: str, handler: Callable[..., Any]) -> None:
        self._handlers.setdefault(event, []).append(handler)

    def start(self) -> None:
        self._client.post("/v1/agents/register", json={
            "name": self.name,
            "type": self.agent_type,
        })
        self._running = True

    def stop(self) -> None:
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running


class StreamMonitorAgent(WaveAgent):
    """Pre-built agent that monitors stream quality."""

    def __init__(
        self,
        api_key: str,
        name: str = "stream-monitor",
        stream_ids: Optional[list[str]] = None,
        auto_remediate: bool = False,
        on_quality_drop: Optional[Callable[..., Any]] = None,
    ) -> None:
        super().__init__(api_key=api_key, name=name, agent_type="stream_monitor")
        self.stream_ids = stream_ids or []
        self.auto_remediate = auto_remediate
        self._on_quality_drop = on_quality_drop

    def check_health(self, stream_id: str) -> dict[str, Any]:
        response = self._client.get(f"/v1/streams/{stream_id}/health")
        response.raise_for_status()
        return response.json()
