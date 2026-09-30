"""Regenerate tests/fixtures/openapi_snapshot.json from the live WAVE OpenAPI document.

    python3 scripts/refresh_openapi_snapshot.py            # fetch https://api.wave.online/openapi.json
    python3 scripts/refresh_openapi_snapshot.py spec.json  # or read a local copy

The snapshot keeps only what the contract test compares: each operation's method, path (relative
to the spec's server URL, which ends in /v1), operationId, and whether it is a product
skill-invocation operation (one that carries ``x-skill-url``). After refreshing, run
``pytest tests/test_contract_coverage.py``: every new operation must be mapped to the SDK method
that sends it, or listed with a reason.
"""
from __future__ import annotations

import datetime
import json
import sys
import urllib.request
from pathlib import Path

SOURCE = "https://api.wave.online/openapi.json"
OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "openapi_snapshot.json"
METHODS = ("get", "post", "put", "patch", "delete")


def load(argv: list[str]) -> dict:
    if len(argv) > 1:
        return json.loads(Path(argv[1]).read_text())
    req = urllib.request.Request(SOURCE, headers={"Accept": "application/json", "User-Agent": "wave-sdk-python-snapshot"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - fixed https URL
        return json.loads(resp.read())


def main(argv: list[str]) -> int:
    spec = load(argv)
    servers = [s.get("url", "") for s in spec.get("servers", [])]
    ops = []
    for path, item in spec["paths"].items():
        for method, op in item.items():
            if method not in METHODS or not isinstance(op, dict):
                continue
            ops.append({
                "method": method.upper(),
                "path": path,
                "operationId": op.get("operationId"),
                "skill_invocation": "x-skill-url" in op,
            })
    ops.sort(key=lambda o: (o["path"], o["method"]))
    snapshot = {
        "source": SOURCE,
        "servers": servers,
        "spec_version": spec.get("info", {}).get("version"),
        "fetched": datetime.date.today().isoformat(),
        "total_paths": len(spec["paths"]),
        "total_ops": len(ops),
        "operations": ops,
    }
    OUT.write_text(json.dumps(snapshot, indent=1) + "\n")
    print(f"wrote {OUT}: {len(ops)} operations across {len(spec['paths'])} paths (spec {snapshot['spec_version']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
