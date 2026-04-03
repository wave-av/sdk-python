"""WAVE SDK - Pulse Analytics API. Streaming analytics and BI."""
from __future__ import annotations
from typing import Any
from wave.client import WaveClient

class PulseAPI:
    def __init__(self, client: WaveClient): self._client = client; self._base = "/v1/analytics"
    def get_stream_analytics(self, stream_id: str, **params: Any) -> dict: return self._client.get(f"{self._base}/streams/{stream_id}", params={k: v for k, v in params.items() if v is not None})
    def get_viewer_analytics(self, **params: Any) -> dict: return self._client.get(f"{self._base}/viewers", params={k: v for k, v in params.items() if v is not None})
    def get_quality_metrics(self, **params: Any) -> dict: return self._client.get(f"{self._base}/quality", params={k: v for k, v in params.items() if v is not None})
    def get_engagement_metrics(self, **params: Any) -> dict: return self._client.get(f"{self._base}/engagement", params={k: v for k, v in params.items() if v is not None})
    def get_revenue_metrics(self, **params: Any) -> dict: return self._client.get(f"{self._base}/revenue", params={k: v for k, v in params.items() if v is not None})
    def get_timeseries(self, metric: str, **params: Any) -> list[dict]: return self._client.get(f"{self._base}/timeseries/{metric}", params={k: v for k, v in params.items() if v is not None})
    def create_report(self, name: str, type: str, time_range: str, format: str = "json") -> dict: return self._client.post(f"{self._base}/reports", json={"name": name, "type": type, "time_range": time_range, "format": format})
    def get_report(self, report_id: str) -> dict: return self._client.get(f"{self._base}/reports/{report_id}")
    def list_reports(self, **params: Any) -> dict: return self._client.get(f"{self._base}/reports", params={k: v for k, v in params.items() if v is not None})
    def list_dashboards(self, **params: Any) -> dict: return self._client.get(f"{self._base}/dashboards", params={k: v for k, v in params.items() if v is not None})
    def create_dashboard(self, name: str, **kwargs: Any) -> dict: return self._client.post(f"{self._base}/dashboards", json={"name": name, **kwargs})
