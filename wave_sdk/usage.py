"""WAVE SDK - Usage API. ``GET /v1/usage``: your organization's own metered totals per dimension.

It needs no resource to exist first, so it is the quickest end-to-end check that a key works::

    report = client.usage.get()
    print(report.org, report.range.days, report.totals.get("wave_search_queries"))

``from_`` and ``to`` are days, as ``YYYYMMDD`` strings or ``datetime.date`` values; both default
to today (UTC) on the server.
"""
from __future__ import annotations

from datetime import date
from typing import Union

from pydantic import BaseModel, ConfigDict, Field

from wave_sdk.client import WaveClient

Day = Union[str, date]


class UsageRange(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    from_: str = Field(alias="from")
    to: str
    days: int


class UsageReport(BaseModel):
    """``totals`` holds raw counters per dimension; ``billable`` the same dimensions in billed units."""

    model_config = ConfigDict(extra="allow")
    org: str
    range: UsageRange
    # A counter the server has no value for arrives as null; one missing counter must not make
    # the whole report unreadable (the meter models failed that way in 2.2.0).
    totals: dict[str, float | None]
    billable: dict[str, float | None] | None = None


def _day(value: Day | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    return value.replace("-", "")


class UsageAPI:
    def __init__(self, client: WaveClient):
        self._client = client

    def get(self, from_: Day | None = None, to: Day | None = None) -> UsageReport:
        """``GET /v1/usage?from=YYYYMMDD&to=YYYYMMDD``."""
        params = {"from": _day(from_), "to": _day(to)}
        return UsageReport(**self._client.get("/v1/usage", params={k: v for k, v in params.items() if v is not None}))
