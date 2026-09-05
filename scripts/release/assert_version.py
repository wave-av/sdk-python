#!/usr/bin/env python3
"""Fail loud if the given tag does not match the project's declared version.

Checks BOTH `pyproject.toml`'s `[project].version` AND `wave_sdk.__version__`
(imported from the checked-out tree, not an installed copy) against the tag.
Used by `release.yml`'s `verify` job right after checking out the tag -- this
is the single source of truth for "does this tag actually match the code",
and it is intentionally a plain script (not inlined YAML) so it can be run
and unit-tested locally without pushing a tag first.

Usage: python3 scripts/release/assert_version.py v2.1.0
Exit 0 if it matches, 1 with a clear message if it does not.
"""
from __future__ import annotations

import sys
from pathlib import Path

import tomllib


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <tag e.g. v2.1.0>", file=sys.stderr)
        return 2

    tag = argv[1]
    tag_version = tag[1:] if tag.startswith("v") else tag
    repo_root = Path(__file__).resolve().parents[2]

    pyproject_path = repo_root / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text())
    pyproject_version = data["project"]["version"]

    sys.path.insert(0, str(repo_root))
    import wave_sdk  # noqa: E402  (import after sys.path fix is intentional here)

    dunder_version = wave_sdk.__version__

    print(f"tag              : {tag} (version {tag_version})")
    print(f"pyproject.toml   : {pyproject_version}")
    print(f"wave_sdk.__version__ : {dunder_version}")

    mismatches = []
    if tag_version != pyproject_version:
        mismatches.append(f"tag {tag_version} != pyproject.toml {pyproject_version}")
    if tag_version != dunder_version:
        mismatches.append(f"tag {tag_version} != wave_sdk.__version__ {dunder_version}")
    if pyproject_version != dunder_version:
        mismatches.append(f"pyproject.toml {pyproject_version} != wave_sdk.__version__ {dunder_version}")

    if mismatches:
        print("VERSION MISMATCH:", file=sys.stderr)
        for m in mismatches:
            print(f" - {m}", file=sys.stderr)
        return 1

    print("OK: tag, pyproject.toml, and wave_sdk.__version__ all agree")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
