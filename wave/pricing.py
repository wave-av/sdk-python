"""WAVE SDK - Pricing Pages API. The seller tier-manifest registry: create,
list, and read manifests for the caller org. The rail law is enforced
server-side - sub-$0.50 tiers must be x402, card requires >= $0.50 - so a
rejected manifest is a law violation, never a silent repricing.

Requires scopes `pricing:write` (create) and `pricing:read` (list/get).
Hosted pages render at pricing.wave.online/<slug> for published manifests.
"""
from __future__ import annotations

from typing import Literal
from wave.client import WaveClient

from pydantic import BaseModel


class PricingTier(BaseModel):
    id: str
    name: str
    price_usdc_micro: str
    rail: Literal["x402", "card", "both"]
    billing: Literal["per_op", "monthly_cap", "volume"]
    features: list[str]


class PricingManifest(BaseModel):
    slug: str
    title: str
    tiers: list[PricingTier]
    contact: str | None = None
    payout: str | None = None


class ManifestCreateResult(BaseModel):
    slug: str
    org: str
    status: Literal["published", "draft", "suspended"]
    updated_at: str


class ManifestListEntry(BaseModel):
    slug: str
    title: str
    status: str
    updated_at: str


class ManifestList(BaseModel):
    org: str
    manifests: list[ManifestListEntry]


class ManifestRead(BaseModel):
    org: str
    slug: str
    status: str
    updated_at: str
    manifest: PricingManifest


class PricingAPI:
    """Pricing Pages API - create, list, and read the caller org's tier manifests."""

    def __init__(self, client: WaveClient):
        self._client = client
        self._base = "/v1/pricing/manifests"

    def create_manifest(self, manifest: PricingManifest) -> ManifestCreateResult:
        """POST /v1/pricing/manifests - validate + upsert a manifest (pricing:write)."""
        return ManifestCreateResult(**self._client.post(self._base, json=manifest.model_dump(exclude_none=True)))

    def list_manifests(self) -> ManifestList:
        """GET /v1/pricing/manifests - list the caller org's manifests (pricing:read)."""
        return ManifestList(**self._client.get(self._base))

    def get_manifest(self, slug: str) -> ManifestRead:
        """GET /v1/pricing/manifests/:slug - read one manifest (pricing:read)."""
        return ManifestRead(**self._client.get(f"{self._base}/{slug}"))
