#!/usr/bin/env bash
# VER-001 — every shipped component resolves to one source revision and version; no newer
# source is represented as deployed.
#
# Thin wrapper around ga_evidence.py, which computes both criteria in one registry-fetch pass
# (VER-001 and SUPPLY-001 share the same PyPI `info.version` lookup). This script filters the
# shared run down to the VER-001 line so it can also be invoked standalone.
#
# Prints one `PASS|FAIL|UNKNOWN VER-001: <detail>` line.
# Exit 0 = pass, 1 = fail, 2 = could not run (never read as a pass).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${GA_OUT_DIR:-$HERE/../../ga-out}"
REPO="${GA_REPO:-wave-av/sdk-python}"
PACKAGE="${GA_PACKAGE:-wave-sdk}"

ARGS=(--out-dir "$OUT_DIR" --repo "$REPO" --package "$PACKAGE")
# GA_EXPECT_VERSION: optional pin asserting PyPI now serves exactly this version (e.g. a release
# job verifying its own publish). Also the deliberate-break lever for the drill this producer's
# PR must prove: pin a wrong version and this check flips PASS/UNKNOWN -> FAIL, exit 1.
[ -n "${GA_EXPECT_VERSION:-}" ] && ARGS+=(--expect-version "$GA_EXPECT_VERSION")

OUTPUT="$(python3 "$HERE/ga_evidence.py" "${ARGS[@]}" 2>&1)"
CODE=$?

echo "$OUTPUT" | grep -E '^(PASS|FAIL|UNKNOWN) VER-001:'
if [ "$CODE" -eq 2 ]; then
  echo "$OUTPUT" 1>&2
  exit 2
fi

echo "$OUTPUT" | grep -q '^FAIL VER-001:' && exit 1
exit 0
