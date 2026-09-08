#!/usr/bin/env python3
"""GA evidence producer for wave-av/sdk-python — VER-001 and SUPPLY-001.

Verifies what the PUBLIC PyPI registry and GitHub actually serve, never the checkout under test
for anything registry-shaped (the checkout only supplies HEAD's own pyproject.toml version and
the git revision, both read-only). See check_ver_001.py and check_supply_001.py for the criteria
themselves; this module is the thin orchestrator: run both, write the two output files, print one
PASS|FAIL|UNKNOWN line per criterion, and set the process exit code.

OUTPUT
  <out>/ga-report.json                        full detail: every observed version/digest/check
  <out>/wave-av__sdk-python.ga-evidence.json   WAVE-GA-gate-spec-v1.0.0 evidence document

EXIT CODES
  0  every criterion is pass or unknown (a criterion that legitimately cannot fully pass yet
     still lets the job succeed; only a real defect or a broken run should redden CI)
  1  at least one criterion is fail
  2  the gate could not run (a registry fetch failed, or similar) — never read as a pass

USAGE
  python3 scripts/ga/ga_evidence.py [--out-dir DIR] [--repo OWNER/NAME] [--package NAME]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_supply_001
import check_ver_001
from ga_common import (
    RegistryError,
    build_document,
    canonical_fingerprint_input,
    git_head_sha,
    sha256_canonical,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(REPO_ROOT / "ga-out"))
    ap.add_argument("--repo", default="wave-av/sdk-python")
    ap.add_argument("--package", default="wave-sdk")
    ap.add_argument(
        "--expect-version",
        default=None,
        help="assert this exact version is what PyPI now serves (e.g. a release job verifying "
        "its own publish); defaults to $GA_EXPECT_VERSION, unset means no assertion",
    )
    args = ap.parse_args()
    expect_version = args.expect_version or os.environ.get("GA_EXPECT_VERSION") or None

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        revision = git_head_sha()
        ver = check_ver_001.run(args.repo, args.package, expect_version=expect_version)
        supply = check_supply_001.run(args.repo, args.package)
    except RegistryError as e:
        sys.stderr.write(f"ga-evidence could not run: {e}\n")
        return 2

    results = [ver, supply]
    fingerprint = sha256_canonical(canonical_fingerprint_input(results))
    verified_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    document = build_document(args.repo, revision, results, verified_at, fingerprint)

    report = {
        "schema": "wave-ga-evidence-sdk-python/1",
        "spec_version": "1.0.0",
        "repository": args.repo,
        "revision": revision,
        "generated_at": verified_at,
        "evidence_sha256": fingerprint,
        "criteria": [
            {
                "criterion_id": r.criterion_id,
                "status": r.status,
                "command": r.command,
                "targets_observed": r.targets_observed,
                "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in r.checks],
            }
            for r in results
        ],
    }

    (out_dir / "ga-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (out_dir / "wave-av__sdk-python.ga-evidence.json").write_text(
        json.dumps(document, indent=2) + "\n", encoding="utf-8"
    )

    exit_code = 0
    for r in results:
        line_status = {"pass": "PASS", "fail": "FAIL", "unknown": "UNKNOWN"}[r.status]
        detail = "; ".join(f"{c.name}={c.ok}" for c in r.checks)
        print(f"{line_status} {r.criterion_id}: {detail}")
        if r.status == "fail":
            exit_code = 1

    print(f"\nevidence fingerprint: {fingerprint}")
    print(f"wrote {out_dir / 'ga-report.json'} and {out_dir / 'wave-av__sdk-python.ga-evidence.json'}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
