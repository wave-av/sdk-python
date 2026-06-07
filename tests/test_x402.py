"""Conformance tests for wave.x402 (EIP-3009 "exact" scheme signing).

These assert the Python signer is byte-for-byte compatible with the reference TypeScript helper in
@wave-av/agent-money (the same viem stack the WAVE facilitator verifies against). The expected values
live in tests/fixtures/x402_exact_vector.json — the canonical cross-language vector every WAVE SDK port
must reproduce. Skips cleanly if the optional `eth-account` extra is not installed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("eth_account", reason='x402 signing needs the extra: pip install "wave-sdk[x402]"')

from wave.x402 import (  # noqa: E402  (after importorskip)
    encode_exact_payment_header,
    get_network_config,
    random_nonce,
    sign_exact_authorization,
)

VECTOR = json.loads((Path(__file__).parent / "fixtures" / "x402_exact_vector.json").read_text())


@pytest.mark.parametrize("v", VECTOR["vectors"], ids=lambda v: v["network"])
def test_signature_is_byte_identical_to_reference(v):
    auth = v["authorization"]
    payload = sign_exact_authorization(
        private_key=VECTOR["payerPrivateKey"],
        network=v["network"],
        to=auth["to"],
        value=auth["value"],
        valid_before=auth["validBefore"],
        valid_after=auth["validAfter"],
        nonce=auth["nonce"],
    )
    assert payload["signature"] == v["signature"]
    assert payload["authorization"] == auth  # wire shape (from/to/value/validAfter/validBefore/nonce)


@pytest.mark.parametrize("v", VECTOR["vectors"], ids=lambda v: v["network"])
def test_payment_header_matches_reference(v):
    auth = v["authorization"]
    payload = sign_exact_authorization(
        private_key=VECTOR["payerPrivateKey"],
        network=v["network"],
        to=auth["to"],
        value=auth["value"],
        valid_before=auth["validBefore"],
        valid_after=auth["validAfter"],
        nonce=auth["nonce"],
    )
    assert encode_exact_payment_header(v["network"], payload) == v["header"]


def test_derives_payer_from_key_and_defaults():
    v = VECTOR["vectors"][0]
    payload = sign_exact_authorization(
        private_key=VECTOR["payerPrivateKey"],
        network="base",
        to=v["authorization"]["to"],
        value=1000,                      # int accepted, stored as decimal string
        valid_before=1900000600,
        nonce=v["authorization"]["nonce"],
    )
    a = payload["authorization"]
    assert a["from"].lower() == VECTOR["payerAddress"].lower()  # derived from the key
    assert a["validAfter"] == "0"                                # default
    assert a["value"] == "1000"                                  # int -> decimal string


def test_random_nonce_is_bytes32_hex():
    n = random_nonce()
    assert n.startswith("0x") and len(n) == 66
    int(n, 16)  # valid hex
    assert random_nonce() != random_nonce()  # fresh each call


def test_from_address_must_match_signer():
    with pytest.raises(ValueError):
        sign_exact_authorization(
            private_key=VECTOR["payerPrivateKey"],
            network="base",
            to=VECTOR["vectors"][0]["authorization"]["to"],
            value="1",
            valid_before="1900000600",
            from_address="0x0000000000000000000000000000000000000001",
        )


def test_unsupported_network_raises():
    with pytest.raises(ValueError):
        sign_exact_authorization(
            private_key=VECTOR["payerPrivateKey"],
            network="ethereum",
            to=VECTOR["vectors"][0]["authorization"]["to"],
            value="1",
            valid_before="1900000600",
        )


def test_get_network_config_returns_copy():
    a = get_network_config("base")
    assert a is not None and a["chainId"] == 8453
    a["chainId"] = 1
    assert get_network_config("base")["chainId"] == 8453  # not mutated
    assert get_network_config("nope") is None
