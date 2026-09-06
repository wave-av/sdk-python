"""VER-001 — every shipped component resolves to one source revision and version; no newer
source is represented as deployed.

Compares: HEAD's pyproject.toml version, PyPI's published `info.version`, the newest `v*` tag on
GitHub, that tag's GitHub Release (if any), and the published wheel's METADATA `Version`. `pass`
only when all agree. HEAD legitimately running ahead of PyPI (an open release PR) is `unknown`
("unreleased source"), never `fail`.
"""
from __future__ import annotations

import hashlib

from ga_common import (
    CheckResult,
    CriterionResult,
    fetch_bytes,
    fetch_json,
    fetch_json_allow_404,
    pypi_url,
    read_head_version,
    semver_tuple,
    status_from_checks,
    wheel_metadata_version,
)


def run(repo: str, package: str, expect_version: str | None = None) -> CriterionResult:
    command = f"python3 scripts/ga/ga_evidence.py --repo {repo} --package {package}"
    if expect_version:
        command += f" --expect-version {expect_version}"
    checks: list[CheckResult] = []
    targets: list[str] = []

    head_version = read_head_version()
    meta = fetch_json(pypi_url(package))
    pypi_version = meta["info"]["version"]
    targets.append(f"{package}@{pypi_version}")

    # Optional pin, analogous to the sdks reference producer's `--versions` pin: a release job
    # can assert the exact version it just published is what PyPI now serves. Never required —
    # only present when the caller (or GA_EXPECT_VERSION) supplies one.
    if expect_version is not None:
        if expect_version == pypi_version:
            checks.append(CheckResult(
                "expected-version-matches-published", True,
                f"expected version {expect_version} == published PyPI version {pypi_version}",
            ))
        else:
            checks.append(CheckResult(
                "expected-version-matches-published", False,
                f"expected version {expect_version} != published PyPI version {pypi_version}",
            ))

    urls = meta.get("urls", [])
    wheel_url = next((u for u in urls if u.get("packagetype") == "bdist_wheel"), None)
    if wheel_url is None:
        checks.append(CheckResult("pypi-wheel-present", False, f"PyPI serves no wheel for {package}=={pypi_version}"))
    else:
        wheel_bytes = fetch_bytes(wheel_url["url"])
        declared_sha = wheel_url.get("digests", {}).get("sha256")
        actual_sha = hashlib.sha256(wheel_bytes).hexdigest()
        if declared_sha and declared_sha != actual_sha:
            checks.append(CheckResult(
                "wheel-digest-matches-index", False,
                f"downloaded {wheel_url['filename']} sha256 {actual_sha} != PyPI-declared {declared_sha}",
            ))
        else:
            checks.append(CheckResult(
                "wheel-digest-matches-index", True,
                f"downloaded {wheel_url['filename']} sha256 matches the PyPI-declared digest",
            ))
        wheel_metadata = wheel_metadata_version(wheel_bytes, wheel_url["filename"])
        if wheel_metadata == pypi_version:
            checks.append(CheckResult(
                "wheel-metadata-matches-pypi-version", True,
                f"wheel METADATA Version {wheel_metadata} == PyPI info.version {pypi_version}",
            ))
        else:
            checks.append(CheckResult(
                "wheel-metadata-matches-pypi-version", False,
                f"wheel METADATA Version {wheel_metadata} != PyPI info.version {pypi_version}",
            ))

    # Newest v* tag and its GitHub release, via the public GitHub API (unauthenticated is fine —
    # this reads public tag/release metadata, never the checkout).
    _, tags = fetch_json_allow_404(f"https://api.github.com/repos/{repo}/tags?per_page=100")
    tag_versions: list[tuple[tuple[int, int, int], str]] = []
    for t in (tags or []):
        name = t.get("name", "")
        if name.startswith("v"):
            sv = semver_tuple(name[1:])
            if sv:
                tag_versions.append((sv, name))

    newest_tag_version = None
    if not tag_versions:
        checks.append(CheckResult("newest-tag-exists", None, "no v* semver tags found on origin"))
    else:
        tag_versions.sort()
        newest_tag = tag_versions[-1][1]
        newest_tag_version = newest_tag[1:]
        checks.append(CheckResult("newest-tag-exists", True, f"newest v* tag is {newest_tag}"))

        rel_status, release = fetch_json_allow_404(f"https://api.github.com/repos/{repo}/releases/tags/{newest_tag}")
        if rel_status == 404:
            checks.append(CheckResult(
                "newest-tag-has-github-release", None,
                f"no GitHub Release object exists for tag {newest_tag}",
            ))
        elif release and release.get("tag_name") == newest_tag:
            checks.append(CheckResult(
                "newest-tag-has-github-release", True,
                f"GitHub Release for {newest_tag} exists and its tag_name matches",
            ))
        else:
            checks.append(CheckResult(
                "newest-tag-has-github-release", False,
                f"GitHub Release for {newest_tag} has tag_name {release.get('tag_name') if release else None!r}",
            ))

    # HEAD vs published: HEAD may legitimately be ahead of PyPI on a pull_request (a release PR
    # that has not published yet) — that is `unknown`, not `fail`.
    head_sv = semver_tuple(head_version)
    pypi_sv = semver_tuple(pypi_version)
    if head_sv is not None and pypi_sv is not None:
        if head_sv == pypi_sv:
            checks.append(CheckResult(
                "head-version-matches-published", True,
                f"HEAD pyproject.toml version {head_version} == published PyPI version {pypi_version}",
            ))
        elif head_sv > pypi_sv:
            checks.append(CheckResult(
                "head-version-matches-published", None,
                f"HEAD pyproject.toml version {head_version} is ahead of published PyPI version "
                f"{pypi_version} — unreleased source, not yet represented as deployed",
            ))
        else:
            checks.append(CheckResult(
                "head-version-matches-published", False,
                f"HEAD pyproject.toml version {head_version} is BEHIND published PyPI version "
                f"{pypi_version} — a newer source is represented as deployed than is checked out",
            ))
    else:
        checks.append(CheckResult(
            "head-version-matches-published", False,
            f"could not parse semver from HEAD version {head_version!r} or PyPI version {pypi_version!r}",
        ))

    # Newest tag vs published version.
    if newest_tag_version is not None:
        newest_tag_sv = semver_tuple(newest_tag_version)
        if newest_tag_sv is not None and pypi_sv is not None:
            if newest_tag_sv == pypi_sv:
                checks.append(CheckResult(
                    "newest-tag-matches-published", True,
                    f"newest tag version {newest_tag_version} == published PyPI version {pypi_version}",
                ))
            elif newest_tag_sv > pypi_sv:
                checks.append(CheckResult(
                    "newest-tag-matches-published", None,
                    f"tag v{newest_tag_version} exists but PyPI still serves {pypi_version} — release "
                    f"pending or the publish step has not completed for this tag",
                ))
            else:
                checks.append(CheckResult(
                    "newest-tag-matches-published", False,
                    f"PyPI serves {pypi_version} but the newest recorded tag is only "
                    f"{newest_tag_version} — the published version has no corresponding source tag",
                ))

    return CriterionResult("VER-001", status_from_checks(checks), command, checks, sorted(set(targets)))
