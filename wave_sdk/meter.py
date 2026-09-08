"""WAVE SDK - Meter API. Read-only metering surface: the ledger (per-window
rows) and rollup (aggregated totals) for the comms productization planes.

Requires scope `meter:read`. Auth, scope, and entitlement are enforced
server-side; the SDK only forwards the API key.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from wave_sdk.client import WaveClient


class MeterMailChannel(BaseModel):
    ops: int; usdc: str; errors: int


class MeterVoiceChannel(BaseModel):
    minutes: float; usdc: str


class MeterSmsChannel(BaseModel):
    ops: int; blocked: int


class MeterRealtimeChannel(BaseModel):
    minutes: float


class MeterStorageChannel(BaseModel):
    bytes: int


class MeterChannels(BaseModel):
    mail: MeterMailChannel; voice: MeterVoiceChannel; sms: MeterSmsChannel
    realtime: MeterRealtimeChannel; storage: MeterStorageChannel


class MeterLedgerRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    org: str
    from_: str = Field(alias="from")
    to: str
    channels: MeterChannels


class MeterLedger(BaseModel):
    rows: list[MeterLedgerRow]
    generated_at: str


class MeterRollupTotals(BaseModel):
    mail: MeterMailChannel; voice: MeterVoiceChannel; sms: MeterSmsChannel
    realtime: MeterRealtimeChannel; storage: MeterStorageChannel


class MeterRollup(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    org: str
    from_: str = Field(alias="from")
    to: str
    totals: MeterRollupTotals
    generated_at: str


class MeterAPI:
    """Meter API - read the org's usage ledger and rollup aggregates. Requires scope `meter:read`."""

    def __init__(self, client: WaveClient):
        self._client = client
        self._base = "/v1/meter"

    def ledger(self, from_: str | None = None, to: str | None = None, channel: Literal["mail", "voice", "sms", "realtime", "storage"] | None = None) -> MeterLedger:
        """Fetch ledger rows for the given time window and optional channel filter."""
        params = {"from": from_, "to": to, "channel": channel}
        return MeterLedger(**self._client.get(f"{self._base}/ledger", params={k: v for k, v in params.items() if v is not None}))

    def rollup(self, from_: str | None = None, to: str | None = None, period: Literal["month", "week", "day"] | None = None) -> MeterRollup:
        """Fetch aggregated rollup totals for the given period."""
        params = {"from": from_, "to": to, "period": period}
        return MeterRollup(**self._client.get(f"{self._base}/ledger/rollup", params={k: v for k, v in params.items() if v is not None}))
