#!/usr/bin/env python3
"""Fail loud if the given tag does not match the project's declared version.

Checks BOTH `pyproject.toml`'s `[project].version` AND `wave_sdk.__version__`
(imported from the checked-out tree, not an installed copy) against the tag.
Used by `release.yml`'s `verify` job right after checking out the tag -- this
is the single source of truth for "does this tag actually match the code",
and it is intentionally a plain script (not inlined YAML) so it can be run
and unit-tested locally without pushing a tag first.

`--repo-root` (default: the current working directory, matching the pattern
already used by scripts/release/check_drift.py) is where pyproject.toml and
the `wave_sdk` package are read from -- deliberately NOT derived from this
script's own file location (`Path(__file__)`). `release.yml` checks out the
release TOOLING (this script) from the workflow's own ref into a separate
`.release-tooling/` path, while the CODE being asserted about is checked out
from the (possibly much older) tag being released -- the two trees are not
siblings once the tooling floats ahead of a backfilled tag, so this script
must never assume "my own directory" is anywhere near the code it inspects.

Usage:
  python3 scripts/release/assert_version.py v2.1.0
  python3 .release-tooling/scripts/release/assert_version.py v2.1.0 --repo-root .
  python3 scripts/release/assert_version.py v2.1.0 --repo-root /path/to/other/checkout

Exit 0 if it matches, 1 with a clear message if it does not, 2 on bad usage.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:  # tomllib is stdlib from 3.11; `tomli` is a dev dependency below that
    # (this repo's pyproject.toml pins `tomli>=2.0.0; python_version < '3.11'`,
    # matching the same fallback already used in tests/test_packaging.py and
    # scripts/release/check_drift.py -- requires-python here is >=3.9, and the
    # `pytest (py3.9)` CI matrix leg runs this script as a subprocess).
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on 3.9/3.10 only
    import tomli as tomllib


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog=Path(argv[0]).name if argv else "assert_version.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("tag", help="tag to check, e.g. v2.1.0")
    parser.add_argument(
        "--repo-root",
        default=".",
        help=(
            "path to the sdk-python checkout whose pyproject.toml/wave_sdk this "
            "validates (default: current working directory -- NOT this script's "
            "own file location, which may live in a separate sparse checkout "
            "pinned to a different ref than the code being verified)"
        ),
    )

    try:
        args = parser.parse_args(argv[1:])
    except SystemExit as exc:
        # argparse already printed a usage message; normalize the exit code
        # to this script's documented "bad usage" code (2) either way.
        return exc.code if isinstance(exc.code, int) else 2

    tag = args.tag
    tag_version = tag[1:] if tag.startswith("v") else tag
    repo_root = Path(args.repo_root).resolve()

    pyproject_path = repo_root / "pyproject.toml"
    if not pyproject_path.is_file():
        print(f"error: {pyproject_path} does not exist -- wrong --repo-root?", file=sys.stderr)
        return 2
    data = tomllib.loads(pyproject_path.read_text())
    pyproject_version = data["project"]["version"]

    sys.path.insert(0, str(repo_root))
    import wave_sdk  # noqa: E402  (import after sys.path fix is intentional here)

    dunder_version = wave_sdk.__version__

    print(f"repo root        : {repo_root}")
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
