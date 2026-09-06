"""Verifies every `client.<namespace>.<method>(` call referenced in README.md's
quickstart resolves to a real attribute on the Wave facade — the README is
documentation the way the SDK actually behaves, not a wish list."""
from __future__ import annotations

import re
from pathlib import Path

README = (Path(__file__).parent.parent / "README.md").read_text()
CALL_RE = re.compile(r"\bclient\.(\w+)\.(\w+)\(")


def test_readme_quickstart_calls_are_real():
    from wave_sdk import Wave
    w = Wave(api_key="test-key")
    calls = sorted(set(CALL_RE.findall(README)))
    assert calls, "expected at least one client.<namespace>.<method>(...) call in README.md"
    missing = []
    for namespace, method in calls:
        ns = getattr(w, namespace, None)
        if ns is None:
            missing.append(f"client.{namespace} (namespace does not exist)")
        elif not hasattr(ns, method):
            missing.append(f"client.{namespace}.{method} (method does not exist)")
    assert not missing, f"README references methods that don't exist: {missing}"
