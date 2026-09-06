"""Unit tests for `wave_sdk.compose` (`ComposeAPI`, `POST /v1/compose`).

Three things this file proves:
  1. Fixture round-trip: `tests/fixtures/compose_proposal.json` parses into
     `ComposeProposal` and `model_dump(by_alias=True)` reproduces it
     byte-identically (field for field, camelCase wire names preserved).
  2. Transport mock: `compose()` issues exactly one request - `POST
     /v1/compose` - and nothing else, whether asserted at the WaveClient
     method boundary (the pattern the rest of this SDK's tests use) or at
     the real httpx transport underneath it.
  3. `save_flow()` makes zero HTTP calls (no machine-auth token exists yet)
     and returns/prints an exact curl for a signed-in console session,
     never a bearer token.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from wave_sdk.client import WaveClient
from wave_sdk.compose import (
    ComposeAPI,
    ComposeProposal,
    QuotedPriceRow,
    UnquotedPriceRow,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "compose_proposal.json"


@pytest.fixture
def fixture_dict() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


@pytest.fixture
def mock_client():
    return MagicMock()


# ---------------------------------------------------------------------------
# 1. Fixture round-trip
# ---------------------------------------------------------------------------


def test_fixture_round_trips_byte_identical(fixture_dict):
    proposal = ComposeProposal.model_validate(fixture_dict)
    dumped = proposal.model_dump(by_alias=True)
    assert dumped == fixture_dict


def test_fixture_price_rows_resolve_to_the_right_variant(fixture_dict):
    proposal = ComposeProposal.model_validate(fixture_dict)
    assert isinstance(proposal.price_rows[0], QuotedPriceRow)
    assert proposal.price_rows[0].usd == 0.025
    assert isinstance(proposal.price_rows[1], UnquotedPriceRow)
    assert proposal.price_rows[1].quote == "quote at call time"


def test_fixture_executes_is_always_false(fixture_dict):
    proposal = ComposeProposal.model_validate(fixture_dict)
    assert proposal.executes is False


def test_fixture_engine_model_is_null(fixture_dict):
    proposal = ComposeProposal.model_validate(fixture_dict)
    assert proposal.engine.model is None


def test_fixture_snake_case_attrs_are_ergonomic(fixture_dict):
    """The Python-facing attribute names are snake_case even though the wire
    fixture is camelCase - both must resolve to the same data."""
    proposal = ComposeProposal.model_validate(fixture_dict)
    assert proposal.product_ids == fixture_dict["productIds"]
    assert proposal.call_shape.http == fixture_dict["callShape"]["http"]
    assert proposal.next_ == fixture_dict["next"]
    assert proposal.grounded_at == fixture_dict["groundedAt"]
    assert proposal.manifest_hash == fixture_dict["manifestHash"]
    assert proposal.flow_id is None


# ---------------------------------------------------------------------------
# 2. Transport: compose() sends exactly one POST /v1/compose, nothing else
# ---------------------------------------------------------------------------


def test_compose_posts_exactly_once_to_v1_compose(mock_client, fixture_dict):
    mock_client.post.return_value = fixture_dict
    api = ComposeAPI(mock_client)
    proposal = api.compose("live captions for tomorrow's webinar", budget_usd=5, flow_id="flw_abc123")

    mock_client.post.assert_called_once_with(
        "/v1/compose",
        json={"intent": "live captions for tomorrow's webinar", "budgetUsd": 5, "flowId": "flw_abc123"},
    )
    mock_client.get.assert_not_called()
    mock_client.put.assert_not_called()
    mock_client.patch.assert_not_called()
    mock_client.delete.assert_not_called()
    assert isinstance(proposal, ComposeProposal)
    assert proposal.id == fixture_dict["id"]


def test_compose_referer_goes_in_context_never_elsewhere(mock_client, fixture_dict):
    mock_client.post.return_value = fixture_dict
    api = ComposeAPI(mock_client)
    api.compose("test intent", referer="captions.wave.online")
    mock_client.post.assert_called_once_with(
        "/v1/compose",
        json={"intent": "test intent", "context": {"referer": "captions.wave.online"}},
    )


def test_get_proposal_reads_by_id(mock_client, fixture_dict):
    mock_client.get.return_value = fixture_dict
    api = ComposeAPI(mock_client)
    proposal = api.get_proposal("prp_webinar_captions_001")
    mock_client.get.assert_called_once_with("/v1/compose/proposals/prp_webinar_captions_001")
    mock_client.post.assert_not_called()
    assert proposal.id == fixture_dict["id"]


def test_compose_only_call_at_the_real_transport_layer(fixture_dict):
    """End-to-end through a real `WaveClient`: exactly one HTTP request
    reaches the transport, and it is `POST /v1/compose` - never any product
    route."""
    requests_seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        return httpx.Response(200, json=fixture_dict)

    client = WaveClient(api_key="test-key")
    client._client = httpx.Client(
        base_url=client.base_url,
        headers=client._build_headers(),
        transport=httpx.MockTransport(handler),
    )
    api = ComposeAPI(client)
    proposal = api.compose("live captions for tomorrow's webinar")

    assert len(requests_seen) == 1
    assert requests_seen[0].method == "POST"
    assert requests_seen[0].url.path == "/v1/compose"
    assert proposal.id == fixture_dict["id"]


# ---------------------------------------------------------------------------
# 3. save_flow(): zero HTTP calls, an honest curl, never a silent no-op
# ---------------------------------------------------------------------------


def test_save_flow_makes_zero_http_calls(mock_client, fixture_dict, capsys):
    proposal = ComposeProposal.model_validate(fixture_dict)
    api = ComposeAPI(mock_client)
    curl = api.save_flow(proposal)

    mock_client.post.assert_not_called()
    mock_client.get.assert_not_called()
    mock_client.put.assert_not_called()
    mock_client.patch.assert_not_called()
    mock_client.delete.assert_not_called()
    assert isinstance(curl, str)


def test_save_flow_curl_names_the_flows_route_and_created_by(mock_client, fixture_dict):
    proposal = ComposeProposal.model_validate(fixture_dict)
    api = ComposeAPI(mock_client)
    curl = api.save_flow(proposal)

    assert "/api/console/flows" in curl
    assert '"createdBy": {"kind": "wave-composer"}' in curl
    assert fixture_dict["manifestHash"] in curl
    assert fixture_dict["groundedAt"] in curl


def test_save_flow_never_adds_a_bearer_token_of_its_own(mock_client, fixture_dict):
    """save_flow()'s own console request carries only a Content-Type header
    and a placeholder Cookie - never an Authorization header, since there is
    no machine-auth token to put in one. (The proposal body it posts may
    itself contain an example product-route curl with its own
    `Authorization: Bearer $WAVE_API_KEY` placeholder - that is data the
    engine generated describing a DIFFERENT call, not a credential this
    method adds.)"""
    proposal = ComposeProposal.model_validate(fixture_dict)
    api = ComposeAPI(mock_client)
    curl = api.save_flow(proposal)

    headers_section = curl.split(" -d '", 1)[0]
    assert "Authorization" not in headers_section
    assert "Cookie: <paste" in headers_section


def test_save_flow_prints_the_curl_it_returns(mock_client, fixture_dict, capsys):
    proposal = ComposeProposal.model_validate(fixture_dict)
    api = ComposeAPI(mock_client)
    curl = api.save_flow(proposal)
    printed = capsys.readouterr().out
    assert curl.strip() in printed
