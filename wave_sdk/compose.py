"""WAVE SDK - Composer API. `POST /v1/compose`: propose a plan across WAVE
products for a plain-English intent. A proposal never executes anything
(`executes` is a literal `False`, never derived) - it is a plan the caller
(human, CLI, SDK, MCP) reads and, if it saves it, becomes a flow.

Field names mirror the public `POST /v1/compose` wire contract exactly.
Python attributes are snake_case for ergonomics; each model aliases its wire
name (`budgetUsd`, `flowId`, `productIds`, `priceRows`, `callShape`,
`groundedAt`, `manifestHash`, `quotedAt`, `validForS`, `promptHash`) so
`model_dump(by_alias=True)` reproduces the exact JSON the API sends and
validates, field for field.

Requires scope `composer:write` (compose) / `composer:read` (get_proposal).
"""
from __future__ import annotations

from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from wave_sdk.client import WaveClient

# The literal every unquoted price row carries. Never computed, never guessed.
QUOTE_AT_CALL_TIME: Literal["quote at call time"] = "quote at call time"

# The meter a successful proposal stamps: free by product decision, counted,
# never billed.
COMPOSE_PROPOSAL_METER = "wave_compose_proposals"

ComposeGrounding = Literal["live", "snapshot"]
ComposeEngineRoute = Literal["dispatch", "deterministic-fallback"]


class ComposeStage(BaseModel):
    """One step of the proposed composition."""

    product: str
    why: str


class ComposeScopeRow(BaseModel):
    """A scope the composition needs, and whether the caller can mint it."""

    scope: str
    mintable: bool
    # Where the mintable fact was read: the open-by-default registry's
    # file:line-ish anchor.
    source: str


class QuotedPriceRow(BaseModel):
    """A price row backed by a live, decodable 402 `quote_token`."""

    model_config = ConfigDict(populate_by_name=True)

    product: str
    meter: str
    usd: float
    unit: str
    quoted_at: int = Field(alias="quotedAt")
    valid_for_s: int = Field(alias="validForS")


class UnquotedPriceRow(BaseModel):
    """No live quote backed this product; the literal reason why, never a
    guessed number."""

    model_config = ConfigDict(populate_by_name=True)

    product: str
    meter: str | None = None
    quote: Literal["quote at call time"] = QUOTE_AT_CALL_TIME
    reason: str


ComposePriceRow = Union[QuotedPriceRow, UnquotedPriceRow]


class ComposeMcpCallShape(BaseModel):
    tool: str
    args: dict[str, Any]


class ComposeCallShape(BaseModel):
    """The one call `next[]` points at: the http curl and, when a WAVE MCP
    tool exists for it, the tool + args shape."""

    model_config = ConfigDict(populate_by_name=True)

    http: str
    mcp: ComposeMcpCallShape | None = None


class ComposeEngineInfo(BaseModel):
    """Which route the engine took and the prompt it used. `model` stays
    `None` until a sourced model catalog exists - the engine never names a
    model it cannot cite."""

    model_config = ConfigDict(populate_by_name=True)

    route: ComposeEngineRoute
    prompt_hash: str = Field(alias="promptHash")
    model: None = None


class ComposeProposal(BaseModel):
    """`POST /v1/compose` response, and the object a saved flow stores.
    Field for field with the API's own `ComposeProposal` wire type."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    intent: str
    stages: list[ComposeStage]
    product_ids: list[str] = Field(alias="productIds")
    tools: list[str]
    scopes: list[ComposeScopeRow]
    price_rows: list[ComposePriceRow] = Field(alias="priceRows")
    call_shape: ComposeCallShape = Field(alias="callShape")
    next_: list[str] = Field(alias="next")
    executes: Literal[False] = False
    grounding: ComposeGrounding
    grounded_at: str = Field(alias="groundedAt")
    manifest_hash: str = Field(alias="manifestHash")
    engine: ComposeEngineInfo
    flow_id: str | None = Field(default=None, alias="flowId")


class ComposeRequest(BaseModel):
    """`POST /v1/compose` request body. `context` orders retrieval only; it
    is never text the model sees."""

    model_config = ConfigDict(populate_by_name=True)

    intent: str
    budget_usd: float | None = Field(default=None, alias="budgetUsd")
    flow_id: str | None = Field(default=None, alias="flowId")
    context: dict[str, str] | None = None


class ComposeAPI:
    """The Composer rendering: `POST /v1/compose` behind `client.compose`.

    Never calls a product route. `compose()` and `get_proposal()` are the
    only network calls this class makes; `save_flow()` deliberately makes
    none (see its docstring).
    """

    def __init__(self, client: WaveClient):
        self._client = client
        self._base = "/v1/compose"

    def compose(
        self,
        intent: str,
        *,
        budget_usd: float | None = None,
        flow_id: str | None = None,
        referer: str | None = None,
    ) -> ComposeProposal:
        """`POST /v1/compose` (composer:write). `intent` is 1..280 chars
        after the API's own sanitizer; `flow_id` re-proposes a saved flow
        against today's manifests; `referer` orders retrieval only."""
        body: dict[str, Any] = {"intent": intent}
        if budget_usd is not None:
            body["budgetUsd"] = budget_usd
        if flow_id is not None:
            body["flowId"] = flow_id
        if referer is not None:
            body["context"] = {"referer": referer}
        return ComposeProposal(**self._client.post(self._base, json=body))

    def get_proposal(self, proposal_id: str) -> ComposeProposal:
        """`GET /v1/compose/proposals/:id` (composer:read) - re-read a stored
        proposal instead of re-composing."""
        return ComposeProposal(**self._client.get(f"{self._base}/proposals/{proposal_id}"))

    def save_flow(
        self,
        proposal: ComposeProposal,
        *,
        console_base_url: str = "https://console.wave.online",
    ) -> str:
        """Save `proposal` as a flow with `createdBy.kind: "wave-composer"`,
        carrying the proposal's `manifestHash` and `groundedAt` so the saved
        flow records what it was grounded on.

        There is no machine-auth token for `wave-composer` callers today -
        the console's flow-save route is session-cookie only until a
        composer:write console token ships (OWED, tracked in the console
        and gateway repos). This method NEVER calls the console route and
        NEVER invents a credential to do so - a silent no-op would be worse
        than an honest gap. It prints, and returns, the exact `curl` a human
        in a signed-in console session can paste to do the save themselves.
        Once the machine-auth token exists, this is the one place that
        gains a `token=` parameter and starts posting for real.
        """
        import json as _json

        body = {
            **proposal.model_dump(by_alias=True, exclude_none=True),
            "createdBy": {"kind": "wave-composer"},
        }
        curl = (
            f"curl -X POST {console_base_url.rstrip('/')}/api/console/flows \\\n"
            '  -H "Content-Type: application/json" \\\n'
            '  -H "Cookie: <paste your signed-in console session cookie>" \\\n'
            f"  -d '{_json.dumps(body)}'"
        )
        print(curl)  # noqa: T201 - the exact curl IS the return value; never a silent no-op.
        return curl
