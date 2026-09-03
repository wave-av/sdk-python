"""WAVE SDK - x402 "exact" scheme signing (EIP-3009 TransferWithAuthorization).

Client-side helper that lets a non-CF agent pay a WAVE x402 facilitator (gateway.wave.online):
sign a USDC `TransferWithAuthorization` as EIP-712 typed data, then encode the X-Payment header.
The signature is cryptographically bound to the payer's wallet; no bearer secret leaves the client,
and the WAVE facilitator (not your server) broadcasts the on-chain pull.

Byte-for-byte compatible with WAVE's reference TypeScript x402 signer — verified against a shared
conformance vector (see ``tests/fixtures/x402_exact_vector.json``).

Signing needs the optional ``eth-account`` dependency::

    pip install "wave-sdk[x402]"

Example::

    >>> from wave_sdk.x402 import sign_exact_authorization, encode_exact_payment_header
    >>> payload = sign_exact_authorization(
    ...     private_key=PAYER_KEY,          # 0x + 64 hex; the agent wallet key, never leaves the client
    ...     network="base",                 # or "base-sepolia"
    ...     to=requirement["payTo"],        # the merchant treasury address
    ...     value=requirement["maxAmountRequired"],   # atomic USDC; must be >= the requirement
    ...     valid_before=int(time.time()) + 600,      # a 10-minute window
    ... )
    >>> header = encode_exact_payment_header("base", payload)
    >>> resp = httpx.get(resource_url, headers={"X-Payment": header})
"""
from __future__ import annotations

import base64
import json
import secrets
from typing import TypedDict


class NetworkConfig(TypedDict):
    chainId: int
    usdc: str
    domainName: str
    domainVersion: str


# USDC EIP-712 domains per network. The domain `name` differs by chain (mainnet "USD Coin" vs Sepolia
# "USDC") — both confirmed on-chain via the token's name()/version() — so the typed-data hash, and thus
# the signature, is chain-specific. Matches WAVE's reference TypeScript x402 EIP-712 domains exactly.
NETWORKS: dict[str, NetworkConfig] = {
    "base": {
        "chainId": 8453,
        "usdc": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
        "domainName": "USD Coin",
        "domainVersion": "2",
    },
    "base-sepolia": {
        "chainId": 84532,
        "usdc": "0x036cbd53842c5426634e7929541ec2318f3dcf7e",
        "domainName": "USDC",
        "domainVersion": "2",
    },
}

# EIP-712 struct for EIP-3009. Field names, Solidity types, and ORDER must match the USDC contract and
# the reference TS helper exactly — any drift changes the hash and the signature verifies as a different
# (or no) payer.
_TRANSFER_WITH_AUTHORIZATION_TYPES = {
    "TransferWithAuthorization": [
        {"name": "from", "type": "address"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"},
    ]
}


class ExactAuthorization(TypedDict):
    from_: str  # serialized as "from" in the wire payload (see _wire_authorization)
    to: str
    value: str
    validAfter: str
    validBefore: str
    nonce: str


class ExactPaymentPayload(TypedDict):
    signature: str
    authorization: dict


def get_network_config(network: str) -> NetworkConfig | None:
    """Return a COPY of the network config for ``network`` ("base" | "base-sepolia"), or None."""
    cfg = NETWORKS.get(network)
    return dict(cfg) if cfg else None  # type: ignore[return-value]


def random_nonce() -> str:
    """A fresh random bytes32 nonce as ``0x`` + 64 lowercase hex chars (single-use, enforced on-chain by
    USDC at settle). Uses ``secrets`` (CSPRNG) — matches the reference helper's ``crypto.getRandomValues``."""
    return "0x" + secrets.token_bytes(32).hex()


def sign_exact_authorization(
    *,
    private_key: str,
    network: str,
    to: str,
    value: str | int,
    valid_before: str | int,
    valid_after: str | int = "0",
    from_address: str | None = None,
    nonce: str | None = None,
) -> ExactPaymentPayload:
    """Sign a USDC EIP-3009 ``TransferWithAuthorization`` for the x402 "exact" scheme.

    Returns ``{"signature": "0x...", "authorization": {from,to,value,validAfter,validBefore,nonce}}`` —
    the same shape the WAVE facilitator's /verify and /settle expect. ``value``/``valid_*`` accept int or
    decimal string and are stored as decimal strings (atomic USDC / unix seconds).

    Raises ImportError if ``eth-account`` is not installed (``pip install "wave-sdk[x402]"``),
    ValueError on an unsupported network or a ``from_address`` that does not match the signing key.
    """
    try:
        from eth_account import Account
        from eth_account.messages import encode_typed_data
    except ImportError as exc:  # pragma: no cover - exercised only without the extra installed
        raise ImportError(
            'x402 signing requires the "eth-account" extra. Install it with: pip install "wave-sdk[x402]"'
        ) from exc

    net = get_network_config(network)
    if net is None:
        raise ValueError(f"unsupported network: {network}")

    account = Account.from_key(private_key)
    sender = from_address or account.address
    if sender.lower() != account.address.lower():
        raise ValueError("from_address does not match the signing key")

    nonce_hex = nonce or random_nonce()
    authorization: ExactAuthorization = {
        "from_": sender,
        "to": to,
        "value": str(value),
        "validAfter": str(valid_after),
        "validBefore": str(valid_before),
        "nonce": nonce_hex,
    }

    signable = encode_typed_data(
        domain_data={
            "name": net["domainName"],
            "version": net["domainVersion"],
            "chainId": net["chainId"],
            "verifyingContract": net["usdc"],
        },
        message_types=_TRANSFER_WITH_AUTHORIZATION_TYPES,
        message_data={
            "from": sender,
            "to": to,
            "value": int(authorization["value"]),
            "validAfter": int(authorization["validAfter"]),
            "validBefore": int(authorization["validBefore"]),
            "nonce": bytes.fromhex(nonce_hex[2:] if nonce_hex.startswith("0x") else nonce_hex),
        },
    )
    signed = account.sign_message(signable)
    signature = "0x" + bytes(signed.signature).hex()

    return {"signature": signature, "authorization": _wire_authorization(authorization)}


def encode_exact_payment_header(network: str, payload: ExactPaymentPayload) -> str:
    """Base64-encode the X-Payment header envelope: ``{x402Version:1, scheme:"exact", network, payload}``.

    Standard (non-URL-safe) base64, matching the reference ``btoa(JSON.stringify(...))``."""
    envelope = {"x402Version": 1, "scheme": "exact", "network": network, "payload": payload}
    return base64.b64encode(json.dumps(envelope, separators=(",", ":")).encode()).decode()


def _wire_authorization(auth: ExactAuthorization) -> dict:
    """Map the internal authorization to the on-the-wire shape (``from_`` -> ``from``)."""
    return {
        "from": auth["from_"],
        "to": auth["to"],
        "value": auth["value"],
        "validAfter": auth["validAfter"],
        "validBefore": auth["validBefore"],
        "nonce": auth["nonce"],
    }
