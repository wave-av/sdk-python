"""WAVE SDK - Pulse Analytics API. Streaming analytics and BI.

The API serves three account-level analytics reads (scope ``analytics:read``):
``get_overview()`` (``GET /v1/analytics/overview``), ``get_top_content()``
(``GET /v1/analytics/top-content``) and ``get_engagement_metrics()``
(``GET /v1/analytics/engagement``). ``from_``/``to`` are ISO-8601 date-times.

The other methods predate the current analytics API and are answered 404 by it today; they raise
:class:`~wave_sdk.client.RouteNotServedError`.
"""
from __future__ import annotations

from typing import Any

from wave_sdk.client import WaveClient


def _window(from_: str | None, to: str | None, **extra: Any) -> dict[str, Any]:
    return {k: v for k, v in {"from": from_, "to": to, **extra}.items() if v is not None}


class PulseAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/analytics"
    def get_overview(self, from_: str | None = None, to: str | None = None) -> dict:
        """``GET /v1/analytics/overview``: account-level totals for the window."""
        result: dict = self._client.get(f"{self._base}/overview", params=_window(from_, to))
        return result
    def get_top_content(self, from_: str | None = None, to: str | None = None, limit: int | None = None) -> dict:
        """``GET /v1/analytics/top-content``: top content by usage (``limit`` 1-100)."""
        result: dict = self._client.get(f"{self._base}/top-content", params=_window(from_, to, limit=limit))
        return result
    def get_engagement_metrics(self, from_: str | None = None, to: str | None = None, **params: Any) -> dict:
        """``GET /v1/analytics/engagement``: account-wide engagement for the window."""
        result: dict = self._client.get(f"{self._base}/engagement", params=_window(from_, to, **params))
        return result
    def get_stream_analytics(self, stream_id: str, **params: Any) -> dict: return self._client.get(f"{self._base}/streams/{stream_id}", params={k: v for k, v in params.items() if v is not None})
    def get_viewer_analytics(self, **params: Any) -> dict: return self._client.get(f"{self._base}/viewers", params={k: v for k, v in params.items() if v is not None})
    def get_quality_metrics(self, **params: Any) -> dict: return self._client.get(f"{self._base}/quality", params={k: v for k, v in params.items() if v is not None})
    def get_revenue_metrics(self, **params: Any) -> dict: return self._client.get(f"{self._base}/revenue", params={k: v for k, v in params.items() if v is not None})
    def get_timeseries(self, metric: str, **params: Any) -> list[dict]: return self._client.get(f"{self._base}/timeseries/{metric}", params={k: v for k, v in params.items() if v is not None})
    def create_report(self, name: str, type: str, time_range: str, format: str = "json") -> dict: return self._client.post(f"{self._base}/reports", json={"name": name, "type": type, "time_range": time_range, "format": format})
    def get_report(self, report_id: str) -> dict: return self._client.get(f"{self._base}/reports/{report_id}")
    def list_reports(self, **params: Any) -> dict: return self._client.get(f"{self._base}/reports", params={k: v for k, v in params.items() if v is not None})
    def list_dashboards(self, **params: Any) -> dict: return self._client.get(f"{self._base}/dashboards", params={k: v for k, v in params.items() if v is not None})
    def create_dashboard(self, name: str, **kwargs: Any) -> dict: return self._client.post(f"{self._base}/dashboards", json={"name": name, **kwargs})
