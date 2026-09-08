#!/usr/bin/env bash
# SUPPLY-001 — release artifacts built by approved CI from an immutable source revision,
# provenance verifiable, SBOM attached.
#
# Thin wrapper around ga_evidence.py (see there for what is and is not machine-verified: the
# provenance clause only — SBOM attachment and known-vuln resolution are named as unverified,
# never assumed). This script filters the shared run down to the SUPPLY-001 line so it can also
# be invoked standalone.
#
# Prints one `PASS|FAIL|UNKNOWN SUPPLY-001: <detail>` line.
# Exit 0 = pass, 1 = fail, 2 = could not run (never read as a pass).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${GA_OUT_DIR:-$HERE/../../ga-out}"
REPO="${GA_REPO:-wave-av/sdk-python}"
PACKAGE="${GA_PACKAGE:-wave-sdk}"

OUTPUT="$(python3 "$HERE/ga_evidence.py" --out-dir "$OUT_DIR" --repo "$REPO" --package "$PACKAGE" 2>&1)"
CODE=$?

echo "$OUTPUT" | grep -E '^(PASS|FAIL|UNKNOWN) SUPPLY-001:'
if [ "$CODE" -eq 2 ]; then
  echo "$OUTPUT" 1>&2
  exit 2
fi

echo "$OUTPUT" | grep -q '^FAIL SUPPLY-001:' && exit 1
exit 0
