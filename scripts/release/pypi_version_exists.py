#!/usr/bin/env python3
"""Check whether PyPI already has an exact version of `wave-sdk`.

Used by `release.yml`'s `publish` job to decide whether to skip the publish
step (idempotent re-runs of `workflow_dispatch` against an already-published
tag must not fail, and must not attempt to re-upload an existing file --
PyPI itself rejects that). Prints `true` or `false` on stdout so a workflow
step can capture it directly into `$GITHUB_OUTPUT`.

Exit 0 whether the version exists or not (that's a successful check). Exit 2
only if PyPI itself could not be read (never treat "unreadable" as "does not
exist" -- that would make an outage silently re-attempt a publish PyPI may
actually already have).

Usage: python3 scripts/release/pypi_version_exists.py 2.1.0
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

PYPI_PROJECT = "wave-sdk"
USER_AGENT = "wave-sdk-release-check (+https://github.com/wave-av/sdk-python)"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <version e.g. 2.1.0>", file=sys.stderr)
        return 2

    version = argv[1]
    url = f"https://pypi.org/pypi/{PYPI_PROJECT}/{version}/json"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            json.loads(resp.read().decode("utf-8"))
        print("true")
        return 0
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            print("false")
            return 0
        print(f"UNREADABLE: PyPI returned HTTP {exc.code} for {url}", file=sys.stderr)
        return 2
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"UNREADABLE: could not read {url}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
