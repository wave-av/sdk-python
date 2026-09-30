"""WAVE SDK - Meter API. Read-only metering surface for the comms productization planes: the
ledger (one metering window with per-channel counters) and the rollup (aggregated totals).

Requires scope `meter:read`. Auth, scope, and entitlement are enforced
server-side; the SDK only forwards the API key.

Every model here accepts fields the SDK does not know yet (``extra="allow"``), and a channel's
``blocked`` is either a count or a reason string (for example ``"a2p-unregistered"``), because
that is what the API returns.
"""
from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from wave_sdk.client import WaveClient

# `blocked` is a count on some channels and a reason string on others.
Blocked = Union[int, str, None]
# Amounts arrive as decimal strings ("0.05"); accept a bare number too.
Amount = Union[str, float]


class _MeterModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


# A counter the response leaves out is None, never 0: a missing value must not read as "no usage".


class MeterMailChannel(_MeterModel):
    ops: int | None = None; usdc: Amount | None = None; errors: int | None = None; blocked: Blocked = None


class MeterVoiceChannel(_MeterModel):
    minutes: float | None = None; usdc: Amount | None = None


class MeterSmsChannel(_MeterModel):
    ops: int | None = None; blocked: Blocked = None


class MeterRealtimeChannel(_MeterModel):
    minutes: float | None = None


class MeterStorageChannel(_MeterModel):
    bytes: int | None = None


class MeterChannels(_MeterModel):
    mail: MeterMailChannel | None = None; voice: MeterVoiceChannel | None = None
    sms: MeterSmsChannel | None = None; realtime: MeterRealtimeChannel | None = None
    storage: MeterStorageChannel | None = None


class MeterLedger(_MeterModel):
    """``GET /v1/meter/ledger``: one metering window for the org."""
    org: str
    from_: str = Field(alias="from")
    to: str
    channels: MeterChannels
    generated_at: str


# Kept so existing imports resolve; the ledger is a single window, not a list of rows.
MeterLedgerRow = MeterLedger


class MeterRollupTotals(MeterChannels):
    pass


class MeterRollup(_MeterModel):
    """``GET /v1/meter/ledger/rollup``: totals aggregated over ``period``."""
    org: str
    from_: str = Field(alias="from")
    to: str
    period: str | None = None
    totals: MeterRollupTotals
    generated_at: str


class MeterAPI:
    """Meter API - read the org's usage ledger and rollup aggregates. Requires scope `meter:read`."""

    def __init__(self, client: WaveClient):
        self._client = client
        self._base = "/v1/meter"

    def ledger(self, from_: str | None = None, to: str | None = None, channel: Literal["mail", "voice", "sms", "realtime", "storage"] | None = None) -> MeterLedger:
        """Fetch the ledger window, optionally bounded by ``from_``/``to`` and filtered by channel."""
        params = {"from": from_, "to": to, "channel": channel}
        return MeterLedger(**self._client.get(f"{self._base}/ledger", params={k: v for k, v in params.items() if v is not None}))

    def rollup(self, from_: str | None = None, to: str | None = None, period: Literal["month", "week", "day"] | None = None) -> MeterRollup:
        """Fetch aggregated rollup totals for the given period."""
        params = {"from": from_, "to": to, "period": period}
        return MeterRollup(**self._client.get(f"{self._base}/ledger/rollup", params={k: v for k, v in params.items() if v is not None}))
