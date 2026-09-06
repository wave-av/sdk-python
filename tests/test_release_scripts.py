"""Unit tests for scripts/release/*.py -- run as subprocesses so a stale
`import wave_sdk` from this test process never leaks into (or masks a bug in)
the script's own import.

The specific regression under test: `.github/workflows/release.yml` checks
out release TOOLING (this script) from the workflow's own ref into a
separate `.release-tooling/` directory, while the CODE it inspects is
checked out from a (possibly much older) release tag into the workspace
root. `scripts/release/assert_version.py` must resolve `pyproject.toml` and
import `wave_sdk` relative to `--repo-root` (default: cwd) -- NEVER relative
to its own file location (`Path(__file__)`) -- or it silently breaks the
moment it is invoked from anywhere other than the tree it is meant to
inspect. This is exactly how the v2.1.0 backfill failed: the tag's tree
predated scripts/release/ entirely, so the workflow's `verify` job could not
even find the script at the in-tree path, let alone run it against the
wrong tree.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSERT_VERSION = REPO_ROOT / "scripts" / "release" / "assert_version.py"


def _write_fake_checkout(tmp_path: Path, version: str) -> Path:
    """Build a minimal standalone checkout with its own pyproject.toml + wave_sdk."""
    checkout = tmp_path / "fake-checkout"
    (checkout / "wave_sdk").mkdir(parents=True)
    (checkout / "pyproject.toml").write_text(
        textwrap.dedent(
            f"""\
            [project]
            name = "wave-sdk"
            version = "{version}"
            """
        )
    )
    (checkout / "wave_sdk" / "__init__.py").write_text(f'__version__ = "{version}"\n')
    return checkout


def _run_assert_version(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ASSERT_VERSION), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_resolves_repo_root_from_cwd_not_from_its_own_file_location(tmp_path):
    """The core regression guard: invoke the script from a directory that is
    NOT anywhere near its own file location (mirrors `.release-tooling/scripts/
    release/assert_version.py` being run against an unrelated tag checkout),
    relying only on cwd defaulting `--repo-root`.
    """
    checkout = _write_fake_checkout(tmp_path, "9.9.9")

    result = _run_assert_version("v9.9.9", cwd=checkout)

    assert result.returncode == 0, result.stderr
    assert "OK: tag, pyproject.toml, and wave_sdk.__version__ all agree" in result.stdout
    assert str(checkout) in result.stdout  # confirms it read the fake checkout, not the real repo


def test_explicit_repo_root_overrides_cwd(tmp_path):
    """`--repo-root` must work even when invoked from a completely different cwd
    (e.g. a workflow step whose default working-directory is the tag checkout,
    but the tooling script lives under `.release-tooling/`)."""
    checkout = _write_fake_checkout(tmp_path, "1.2.3")

    result = _run_assert_version("v1.2.3", "--repo-root", str(checkout), cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert "OK: tag, pyproject.toml, and wave_sdk.__version__ all agree" in result.stdout


def test_fails_loud_on_version_mismatch(tmp_path):
    checkout = _write_fake_checkout(tmp_path, "1.0.0")

    result = _run_assert_version("v2.0.0", cwd=checkout)

    assert result.returncode == 1
    assert "VERSION MISMATCH" in result.stderr
    assert "tag 2.0.0 != pyproject.toml 1.0.0" in result.stderr


def test_fails_with_usage_code_on_missing_tag_argument(tmp_path):
    checkout = _write_fake_checkout(tmp_path, "1.0.0")

    result = _run_assert_version(cwd=checkout)

    assert result.returncode == 2


def test_fails_clearly_on_wrong_repo_root(tmp_path):
    """A --repo-root that doesn't contain pyproject.toml must fail loud (exit 2),
    not crash with an unhandled traceback or silently read the wrong tree."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    result = _run_assert_version("v1.0.0", "--repo-root", str(empty_dir), cwd=tmp_path)

    assert result.returncode == 2
    assert "does not exist" in result.stderr


def test_real_repo_checkout_passes_when_invoked_from_a_different_cwd(tmp_path):
    """Regression check against the ACTUAL repo: running the script with the
    real repo root passed via --repo-root, from an unrelated cwd, must still
    resolve pyproject.toml/wave_sdk from --repo-root, not from cwd or from
    the script's own directory.
    """
    result = _run_assert_version(
        f"v{_current_repo_version()}",
        "--repo-root",
        str(REPO_ROOT),
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr


def _current_repo_version() -> str:
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - exercised on 3.9/3.10 only
        import tomli as tomllib

    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    return data["project"]["version"]
