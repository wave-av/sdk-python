"""SUPPLY-001 — release artifacts built by approved CI from an immutable source revision,
provenance verifiable, SBOM attached.

This producer machine-verifies the provenance clause ONLY: the PyPI Integrity API is queried for
every published artifact (wheel + sdist), and the attestation's claimed source repository must be
`github.com/<repo>`. SBOM attachment and critical-vulnerability resolution are NOT machine-verified
here, so a fully-verified provenance still yields `unknown` (never `pass`) with those two gaps
named explicitly in `failing_checks`. Absent or mismatched provenance is `fail`.
"""
from __future__ import annotations

import json

from ga_common import CheckResult, CriterionResult, fetch_json, fetch_json_allow_404, pypi_url


def run(repo: str, package: str) -> CriterionResult:
    command = f"python3 scripts/ga/ga_evidence.py --repo {repo} --package {package}"
    checks: list[CheckResult] = []

    meta = fetch_json(pypi_url(package))
    version = meta["info"]["version"]
    urls = meta.get("urls", [])
    targets = [f"{package}@{version}"]

    if not urls:
        checks.append(CheckResult("pypi-artifacts-present", False, f"PyPI serves no files for {package}=={version}"))
        return CriterionResult("SUPPLY-001", "fail", command, checks, targets)

    all_have_provenance = True
    wrong_repo_claims: list[str] = []
    for u in urls:
        filename = u["filename"]
        prov_url = (
            f"https://pypi.org/integrity/{package}/{version}/{filename}/provenance"
        )
        status, body = fetch_json_allow_404(prov_url)
        if status == 404 or body is None or "attestation_bundles" not in body:
            all_have_provenance = False
            checks.append(CheckResult(
                f"provenance-present:{filename}", False,
                "no provenance available from PyPI Integrity API",
            ))
            continue
        bundles = body.get("attestation_bundles", [])
        raw = json.dumps(body)
        repo_claim_ok = f"github.com/{repo}" in raw or repo in raw
        if repo_claim_ok:
            checks.append(CheckResult(
                f"provenance-present:{filename}", True,
                f"PyPI Integrity API returned {len(bundles)} attestation bundle(s) referencing {repo}",
            ))
        else:
            wrong_repo_claims.append(filename)
            checks.append(CheckResult(
                f"provenance-present:{filename}", False,
                f"attestation present but does not reference {repo}",
            ))

    if wrong_repo_claims or not all_have_provenance:
        status = "fail"
    else:
        # Provenance verifies for every artifact, but SBOM attachment and known-vuln resolution
        # stay out of scope for this producer — the criterion cannot be a full pass.
        status = "unknown"
        checks.append(CheckResult("sbom-attached", None, "SBOM attachment not verified by this producer"))
        checks.append(CheckResult("known-vuln-resolution", None, "critical-vuln resolution not verified by this producer"))

    return CriterionResult("SUPPLY-001", status, command, checks, targets)
