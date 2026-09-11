#!/usr/bin/env python3
"""Fail loud unless an SPDX SBOM enumerates wave-sdk AND every unconditional
runtime dependency the installed wheel declares.

Used by `release.yml`'s `sbom` job after syft has scanned the INSTALLED tree
(`pip install --target <dir> <published wheel>`). The check this replaces
only asserted `packages[]` was non-empty -- which an SBOM generated from a
bare, never-installed wheel satisfied with a single self-describing entry and
zero dependencies. That is the defect: an SBOM that predates install is a
claim, not an inventory.

The floor is derived from the installed wheel's OWN metadata (`Requires-Dist`
in `<name>-<version>.dist-info/METADATA` under `--target`), not from a
hardcoded list, so it tracks `pyproject.toml` as dependencies change. Only
UNCONDITIONAL requirements count (no `;` marker): extras and
`python_version`-gated dependencies are legitimately absent from the release
runner's interpreter. Names are compared PEP 503-normalized on both sides so
`pydantic_core` (dist-info) and `pydantic-core` (syft) agree.

Deliberately a plain stdlib script (not inlined YAML) so it can be run and
unit-tested locally against a real or synthetic SBOM without pushing a tag.
Like the other scripts here it is invoked from `.release-tooling/` and never
assumes anything about its own file location.

Usage:
  python3 scripts/release/validate_sbom.py wave_sdk-2.2.0.spdx.json \
      --target sbom-env --version 2.2.0

Exit 0 if the SBOM passes, 1 with a `::error::` line if it does not, 2 on bad
usage (missing file / no installed distribution to derive a floor from).
"""
from __future__ import annotations

import argparse
import importlib.metadata as md
import json
import re
import sys
from pathlib import Path

DIST_NAME = "wave-sdk"
_NO_VERSION = (None, "", "NOASSERTION")
_REQ_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class ValidationError(Exception):
    """A checked, expected validation failure (exit 1)."""


class UsageError(Exception):
    """Inputs are unusable rather than merely failing the check (exit 2)."""


def normalize(name: str) -> str:
    """PEP 503 name normalization."""
    return re.sub(r"[-_.]+", "-", name).lower()


def installed_distribution(target: Path, name: str = DIST_NAME) -> md.Distribution:
    """Find exactly one installed distribution called `name` under `target`.

    Discovers every `*.dist-info` on `target` and filters by normalized
    metadata `Name`, rather than relying on `discover(name=...)`, whose own
    normalization behaviour differs across Python versions.
    """
    if not target.is_dir():
        raise UsageError(f"--target {target} is not a directory")
    wanted = normalize(name)
    found = [
        d for d in md.Distribution.discover(path=[str(target)])
        if normalize(d.metadata["Name"] or "") == wanted
    ]
    if len(found) != 1:
        raise UsageError(f"expected exactly one installed {name} under {target}, found {len(found)}")
    return found[0]


def unconditional_requirements(dist: md.Distribution) -> set[str]:
    """Normalized names of the distribution's runtime deps that carry no marker."""
    names: set[str] = set()
    for req in dist.requires or []:
        if ";" in req:
            continue
        match = _REQ_NAME.match(req.strip())
        if match:
            names.add(normalize(match.group(0)))
    return names


def versioned_package_names(doc: dict) -> set[str]:
    """Normalized names of SBOM packages[] entries that carry a real version."""
    return {
        normalize(p["name"])
        for p in doc.get("packages") or []
        if p.get("name") and p.get("versionInfo") not in _NO_VERSION
    }


def validate(sbom_file: Path, target: Path, version: str | None) -> str:
    """Return a one-line summary on success; raise ValidationError/UsageError otherwise."""
    if not sbom_file.is_file() or sbom_file.stat().st_size == 0:
        raise UsageError(f"{sbom_file} is missing or empty")
    with sbom_file.open(encoding="utf-8") as fh:
        doc = json.load(fh)
    packages = doc.get("packages") or []
    if not packages:
        raise ValidationError(f"{sbom_file} has an empty packages[] array")

    dist = installed_distribution(target)
    if version is not None and dist.version != version:
        raise ValidationError(f"installed {DIST_NAME} version {dist.version} != release version {version}")

    required = unconditional_requirements(dist)
    if not required:
        raise ValidationError(
            f"installed {DIST_NAME} declares no unconditional runtime dependencies "
            "-- refusing to validate against a floor of 0"
        )

    expected = {normalize(DIST_NAME)} | required
    versioned = versioned_package_names(doc)
    missing = sorted(expected - versioned)
    floor = len(expected)
    summary = (
        f"SBOM {doc.get('spdxVersion')}: {len(packages)} packages[], {len(versioned)} with a real "
        f"versionInfo; floor {floor} ({DIST_NAME} + {len(required)} declared runtime deps: "
        f"{', '.join(sorted(required))})"
    )
    if missing:
        raise ValidationError(
            f"{summary}\n::error::sbom: missing versioned entries for: {', '.join(missing)} "
            "-- syft likely scanned an uninstalled tree"
        )
    if len(versioned) < floor:
        raise ValidationError(f"{summary}\n::error::sbom: only {len(versioned)} versioned package(s), below the floor of {floor}")
    return summary


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sbom_file", type=Path, help="SPDX JSON produced from the installed tree")
    parser.add_argument("--target", type=Path, required=True, help="directory `pip install --target` populated")
    parser.add_argument("--version", default=None, help="release version the installed wheel must carry")
    args = parser.parse_args(argv[1:])

    try:
        summary = validate(args.sbom_file, args.target, args.version)
    except ValidationError as exc:
        print(f"::error::sbom: {exc}", file=sys.stderr)
        return 1
    except UsageError as exc:
        print(f"::error::sbom: {exc}", file=sys.stderr)
        return 2
    print(summary)
    print(f"SBOM OK: {DIST_NAME} and every declared runtime dependency are enumerated")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
