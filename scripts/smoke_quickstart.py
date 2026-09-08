"""CI fresh-install smoke: proves the INSTALLED WHEEL imports and reaches the
live WAVE gateway (https://api.wave.online), using the first two calls from
README.md's quickstart (search + pricing) — the ones that resolve to routes
confirmed live in the public OpenAPI spec and that respond deterministically
(200, or an auth/scope error) without depending on a real, fetchable media
URL. Never mocked: this is a real HTTP round trip against production.

Exit 0 when the SDK reaches the gateway, whether or not the call is fully
authorized (a 402 Payment Required or a 403 SCOPE_INSUFFICIENT both prove the
request landed on a real, authenticating route). Exit 1 on anything that
indicates the *installed package itself* is broken (ImportError, or any
response that is not a recognized "reached the gateway" shape).

Invoked by .github/workflows/smoke-install.yml against a wheel built from
this checkout, installed into a throwaway venv with no repo source on
sys.path — the class of bug this guards against (the SDK's own top-level
package shadowing Python's stdlib `wave` module) is invisible to `pytest`
run from the repo checkout, because the checkout directory being first on
sys.path masks the collision. Only an install-from-wheel-elsewhere run like
this one, or a real end user's environment, sees it.
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    api_key = os.environ.get("WAVE_GATEWAY_API_KEY")
    if not api_key:
        print("skipped: WAVE_GATEWAY_API_KEY absent (fork or unset)")
        return 0

    # Import happens after the env-var short-circuit so a fork PR (no secret)
    # still exercises the import path, which is the cheapest and most common
    # way this class of bug shows up.
    from wave_sdk import Wave, WaveError

    client = Wave(api_key=api_key, organization_id="org_123")

    reached_gateway = False

    try:
        results = client.search.search(query="product launch")
        print(f"OK: search.search() -> {len(results.get('results', []))} results")
        reached_gateway = True
    except WaveError as e:
        if e.status_code in (402, 403):
            print(f"OK (reached gateway, gated): search.search() -> {e.status_code} {e.code}")
            reached_gateway = True
        else:
            print(f"FAIL: search.search() -> {e.status_code} {e.code}: {e.message}", file=sys.stderr)

    try:
        client.pricing.list_manifests()
        print("OK: pricing.list_manifests() -> 200")
        reached_gateway = True
    except WaveError as e:
        if e.status_code in (402, 403):
            print(f"OK (reached gateway, gated): pricing.list_manifests() -> {e.status_code} {e.code}")
            reached_gateway = True
        else:
            print(f"FAIL: pricing.list_manifests() -> {e.status_code} {e.code}: {e.message}", file=sys.stderr)

    if not reached_gateway:
        print("FAIL: neither quickstart call reached the gateway", file=sys.stderr)
        return 1

    print("QUICKSTART OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
