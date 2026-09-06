"""Shared primitives for the GA evidence producer: registry fetch, semver, and the evidence
document shape. Stdlib only. Nothing here reads the checkout for anything registry-shaped —
only `read_head_version()` and `git_head_sha()` do, and both are read-only.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

import tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
USER_AGENT = "wave-ga-evidence-sdk-python/1.0"
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)")


class RegistryError(RuntimeError):
    """Raised when a public registry cannot be reached — always exit 2, never a pass."""


def semver_tuple(v: str) -> tuple[int, int, int] | None:
    m = SEMVER_RE.match(v.strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def fetch_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        raise RegistryError(f"GET {url} failed: {type(e).__name__}: {e}") from e


def fetch_json_allow_404(url: str, timeout: int = 30) -> tuple[int, dict | None]:
    """Like fetch_json but a 404 is a normal, expected outcome — not a registry failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return 404, None
        raise RegistryError(f"GET {url} failed: HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        raise RegistryError(f"GET {url} failed: {type(e).__name__}: {e}") from e


def fetch_bytes(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        raise RegistryError(f"GET {url} failed: {type(e).__name__}: {e}") from e


def pypi_url(package: str, suffix: str = "") -> str:
    base = f"https://pypi.org/pypi/{quote(package)}/json"
    return base if not suffix else f"{base}/{suffix}"


def wheel_metadata_version(wheel_bytes: bytes, filename: str) -> str:
    with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as zf:
        metadata_names = [n for n in zf.namelist() if n.endswith(".dist-info/METADATA")]
        if not metadata_names:
            raise RegistryError(f"{filename}: no *.dist-info/METADATA member in wheel")
        text = zf.read(metadata_names[0]).decode("utf-8", errors="replace")
    for line in text.splitlines():
        if line.startswith("Version:"):
            return line.split(":", 1)[1].strip()
    raise RegistryError(f"{filename}: METADATA has no Version: field")


def read_head_version() -> str:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text("utf-8"))
    return data["project"]["version"]


def git_head_sha() -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise RegistryError(f"git rev-parse HEAD failed: {r.stderr.strip()}")
    return r.stdout.strip()


@dataclass
class CheckResult:
    name: str
    ok: bool | None  # True=pass-contributing, False=fail-contributing, None=unknown-contributing
    detail: str


@dataclass
class CriterionResult:
    criterion_id: str
    status: str  # pass | fail | unknown
    command: str
    checks: list[CheckResult] = field(default_factory=list)
    targets_observed: list[str] = field(default_factory=list)


def status_from_checks(checks: list[CheckResult]) -> str:
    ok_vals = [c.ok for c in checks]
    if any(v is False for v in ok_vals):
        return "fail"
    if any(v is None for v in ok_vals):
        return "unknown"
    return "pass"


def canonical_fingerprint_input(results: list[CriterionResult]) -> dict:
    """Fingerprint input: criterion ids, check names, ok flags, observed versions/digests.
    Deliberately excludes timestamps, temp paths and durations so two runs against the same
    published artifacts produce the same digest."""
    rows = []
    for r in sorted(results, key=lambda r: r.criterion_id):
        rows.append({
            "criterion_id": r.criterion_id,
            "status": r.status,
            "targets_observed": sorted(r.targets_observed),
            "checks": sorted([[c.name, c.ok] for c in r.checks]),
        })
    return {"rows": rows}


def sha256_canonical(obj: dict) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def build_document(repo: str, revision: str, results: list[CriterionResult], verified_at: str, fingerprint: str) -> dict:
    out_results = []
    for r in sorted(results, key=lambda r: r.criterion_id):
        entry = {
            "criterion_id": r.criterion_id,
            "status": r.status,
            "command": r.command,
            "evidence_sha256": fingerprint,
            "evidence_uri": "ci://wave-av/sdk-python/.github/workflows/ga-evidence.yml#ga-report.json",
            "verified_at": verified_at,
        }
        if r.targets_observed:
            entry["targets_observed"] = r.targets_observed
        failing = [f"{c.name}: {c.detail}" for c in r.checks if c.ok is False] + \
                  [f"{c.name}: {c.detail}" for c in r.checks if c.ok is None]
        if failing:
            entry["failing_checks"] = failing
        out_results.append(entry)
    return {
        "spec_version": "1.0.0",
        "repository": repo,
        "revision": revision,
        "results": out_results,
    }
