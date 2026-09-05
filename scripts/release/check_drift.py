#!/usr/bin/env python3
"""Release-drift detector for wave-av/sdk-python (PyPI package `wave-sdk`).

Compares four sources of truth and fails loud the moment any two disagree:
  1. the latest git tag on the local checkout (or `--tag` override)
  2. the project version declared in `pyproject.toml` on the checked-out ref
  3. the latest version PyPI serves (`https://pypi.org/pypi/wave-sdk/json`)
  4. whether a GitHub Release exists for that tag (`gh api repos/<repo>/releases/tags/<tag>`)

It also checks PyPI's PEP 740 attestation/provenance field
(`urls[].provenance` in `https://pypi.org/pypi/wave-sdk/<version>/json`) for
the latest published version, and fails if no file carries one.

Exit codes (checked by both workflows and safe to script against):
  0  everything agrees, release exists, attestation present
  1  drift detected (a real, verified disagreement)
  2  a source was unreadable (network error, bad JSON, git/gh failure) --
     an unreadable registry is NEVER treated as "in sync"

Stdlib + `git`/`gh` CLI only. No third-party imports so this runs identically
in CI and on a laptop with nothing but Python 3.11+ and the GitHub CLI.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import tomllib

PYPI_PROJECT = "wave-sdk"
GITHUB_REPO = "wave-av/sdk-python"
USER_AGENT = "wave-sdk-release-drift-check (+https://github.com/wave-av/sdk-python)"


class UnreadableError(Exception):
    """A source could not be read at all (distinct from "read and disagrees")."""


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise
        raise UnreadableError(f"HTTP {exc.code} fetching {url}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise UnreadableError(f"could not read {url}: {exc}") from exc


def pypi_latest_version() -> str:
    try:
        data = _http_get_json(f"https://pypi.org/pypi/{PYPI_PROJECT}/json")
    except urllib.error.HTTPError as exc:
        raise UnreadableError(f"PyPI project page returned HTTP {exc.code}") from exc
    try:
        return data["info"]["version"]
    except (KeyError, TypeError) as exc:
        raise UnreadableError("PyPI JSON response missing info.version") from exc


def pypi_attestations(version: str) -> tuple[bool, list[str]]:
    """Return (any_attested, [filenames missing provenance])."""
    try:
        data = _http_get_json(f"https://pypi.org/pypi/{PYPI_PROJECT}/{version}/json")
    except urllib.error.HTTPError as exc:
        raise UnreadableError(f"PyPI release page for {version} returned HTTP {exc.code}") from exc
    urls = data.get("urls")
    if not isinstance(urls, list) or not urls:
        raise UnreadableError(f"PyPI release page for {version} has no urls[] to check for provenance")
    missing = [u.get("filename", "<unknown>") for u in urls if not u.get("provenance")]
    any_attested = any(u.get("provenance") for u in urls)
    return any_attested, missing


def project_version(repo_root: Path) -> str:
    pyproject = repo_root / "pyproject.toml"
    try:
        data = tomllib.loads(pyproject.read_text())
    except OSError as exc:
        raise UnreadableError(f"could not read {pyproject}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise UnreadableError(f"could not parse {pyproject}: {exc}") from exc
    try:
        return data["project"]["version"]
    except (KeyError, TypeError) as exc:
        raise UnreadableError(f"{pyproject} has no [project].version") from exc


def latest_git_tag(repo_root: Path, override: str | None) -> str:
    if override:
        return override
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "tag", "--list", "v*", "--sort=-v:refname"],
            capture_output=True,
            text=True,
            check=True,
            timeout=20,
        )
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as exc:
        raise UnreadableError(f"could not list git tags: {exc}") from exc
    tags = [t for t in out.stdout.splitlines() if t.strip()]
    if not tags:
        raise UnreadableError("no v*-pattern git tags found")
    return tags[0]


def github_release_exists(tag: str) -> bool | None:
    """True/False if the API answered, None if gh CLI itself is unavailable."""
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{GITHUB_REPO}/releases/tags/{tag}"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UnreadableError(f"could not invoke gh CLI: {exc}") from exc
    if result.returncode == 0:
        return True
    if "HTTP 404" in result.stderr or "Not Found" in result.stderr:
        return False
    raise UnreadableError(f"gh api releases/tags/{tag} failed: {result.stderr.strip()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="path to the sdk-python checkout")
    parser.add_argument("--tag", default=None, help="override the git-tag source of truth (skips git tag --list)")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()

    findings: list[str] = []
    drift = False

    try:
        tag = latest_git_tag(repo_root, args.tag)
        tag_version = tag[1:] if tag.startswith("v") else tag
        print(f"[source] latest git tag           : {tag} (version {tag_version})")
    except UnreadableError as exc:
        print(f"[UNREADABLE] git tag: {exc}", file=sys.stderr)
        return 2

    try:
        pv = project_version(repo_root)
        print(f"[source] pyproject.toml version    : {pv}")
    except UnreadableError as exc:
        print(f"[UNREADABLE] pyproject.toml: {exc}", file=sys.stderr)
        return 2

    try:
        pypi_v = pypi_latest_version()
        print(f"[source] PyPI latest version        : {pypi_v}")
    except UnreadableError as exc:
        print(f"[UNREADABLE] PyPI project json: {exc}", file=sys.stderr)
        return 2

    try:
        released = github_release_exists(tag)
        print(f"[source] GitHub Release for {tag}   : {'exists' if released else 'MISSING'}")
    except UnreadableError as exc:
        print(f"[UNREADABLE] GitHub Release lookup: {exc}", file=sys.stderr)
        return 2

    try:
        attested, missing = pypi_attestations(pypi_v)
        if attested and not missing:
            print(f"[source] PyPI {pypi_v} attestations : present on all files")
        elif attested:
            print(f"[source] PyPI {pypi_v} attestations : PARTIAL, missing on {missing}")
        else:
            print(f"[source] PyPI {pypi_v} attestations : NONE (urls[].provenance is null on every file)")
    except UnreadableError as exc:
        print(f"[UNREADABLE] PyPI attestation lookup: {exc}", file=sys.stderr)
        return 2

    if tag_version != pv:
        findings.append(f"DRIFT: git tag {tag} (version {tag_version}) != pyproject.toml version {pv}")
        drift = True
    if pypi_v != tag_version:
        findings.append(f"DRIFT: PyPI latest ({pypi_v}) != latest tag version ({tag_version})")
        drift = True
    if not released:
        findings.append(f"DRIFT: no GitHub Release exists for tag {tag}")
        drift = True
    if not attested or missing:
        findings.append(f"DRIFT: PyPI {pypi_v} is missing PEP 740 attestation/provenance on: {missing or 'all files'}")
        drift = True

    print()
    if drift:
        print("RESULT: DRIFT DETECTED")
        for f in findings:
            print(f" - {f}")
        return 1

    print("RESULT: in sync (tag, pyproject, PyPI, GitHub Release, and attestations all agree)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
