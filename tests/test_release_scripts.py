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

import json
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


# ---------------------------------------------------------------------------
# scripts/release/validate_sbom.py -- the SBOM must enumerate what ships.
#
# Regression under test: release.yml's `sbom` job used to point syft at a
# bare, never-installed wheel, producing a one-entry SBOM with zero runtime
# dependencies that the old "packages[] is non-empty" check waved through.
# The validator derives its floor from the INSTALLED wheel's Requires-Dist
# (under --target) and fails loud when any unconditional dependency is absent.
# ---------------------------------------------------------------------------
VALIDATE_SBOM = REPO_ROOT / "scripts" / "release" / "validate_sbom.py"

_FAKE_REQUIRES = [
    "httpx>=0.25.0",
    "pydantic>=2.0.0",
    'eval-type-backport>=0.2.0; python_version < "3.10"',  # marker-gated: not part of the floor
    'websocket-client>=1.0.0; extra == "realtime"',  # extra: not part of the floor
]


def _write_fake_target(tmp_path: Path, version: str = "9.9.9", requires=_FAKE_REQUIRES) -> Path:
    """A minimal `pip install --target`-shaped tree: just wave-sdk's dist-info."""
    target = tmp_path / "sbom-env"
    dist_info = target / f"wave_sdk-{version}.dist-info"
    dist_info.mkdir(parents=True)
    lines = ["Metadata-Version: 2.1", "Name: wave-sdk", f"Version: {version}"]
    lines += [f"Requires-Dist: {req}" for req in requires]
    (dist_info / "METADATA").write_text("\n".join(lines) + "\n")
    return target


def _write_sbom(tmp_path: Path, packages: list) -> Path:
    sbom = tmp_path / "wave_sdk-9.9.9.spdx.json"
    sbom.write_text(json.dumps({"spdxVersion": "SPDX-2.3", "packages": packages}))
    return sbom


def _pkg(name: str, version: str | None = "1.0.0") -> dict:
    entry = {"name": name}
    if version is not None:
        entry["versionInfo"] = version
    return entry


def _run_validate_sbom(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATE_SBOM), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_validate_sbom_passes_when_every_unconditional_dependency_is_enumerated(tmp_path):
    target = _write_fake_target(tmp_path)
    # syft reports dist-info names as-is; underscores must normalize to match.
    sbom = _write_sbom(tmp_path, [_pkg("wave_sdk", "9.9.9"), _pkg("httpx"), _pkg("pydantic"), _pkg("pydantic_core")])

    result = _run_validate_sbom(str(sbom), "--target", str(target), "--version", "9.9.9", cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert "floor 3 (wave-sdk + 2 declared runtime deps: httpx, pydantic)" in result.stdout
    assert "SBOM OK" in result.stdout


def test_validate_sbom_fails_loud_on_the_uninstalled_wheel_shape(tmp_path):
    """The exact defect: a single self-describing entry and no dependencies."""
    target = _write_fake_target(tmp_path)
    sbom = _write_sbom(tmp_path, [_pkg("wave-sdk", "9.9.9")])

    result = _run_validate_sbom(str(sbom), "--target", str(target), "--version", "9.9.9", cwd=tmp_path)

    assert result.returncode == 1
    assert "::error::sbom:" in result.stderr
    assert "missing versioned entries for: httpx, pydantic" in result.stderr


def test_validate_sbom_ignores_entries_without_a_real_version(tmp_path):
    target = _write_fake_target(tmp_path)
    sbom = _write_sbom(tmp_path, [_pkg("wave-sdk", "9.9.9"), _pkg("httpx", "NOASSERTION"), _pkg("pydantic", None)])

    result = _run_validate_sbom(str(sbom), "--target", str(target), cwd=tmp_path)

    assert result.returncode == 1
    assert "missing versioned entries for: httpx, pydantic" in result.stderr


def test_validate_sbom_fails_on_empty_packages(tmp_path):
    target = _write_fake_target(tmp_path)
    sbom = _write_sbom(tmp_path, [])

    result = _run_validate_sbom(str(sbom), "--target", str(target), cwd=tmp_path)

    assert result.returncode == 1
    assert "empty packages[]" in result.stderr


def test_validate_sbom_fails_on_release_version_mismatch(tmp_path):
    target = _write_fake_target(tmp_path, version="9.9.9")
    sbom = _write_sbom(tmp_path, [_pkg("wave-sdk", "9.9.9"), _pkg("httpx"), _pkg("pydantic")])

    result = _run_validate_sbom(str(sbom), "--target", str(target), "--version", "1.0.0", cwd=tmp_path)

    assert result.returncode == 1
    assert "installed wave-sdk version 9.9.9 != release version 1.0.0" in result.stderr


def test_validate_sbom_refuses_a_floor_of_zero(tmp_path):
    target = _write_fake_target(tmp_path, requires=['websocket-client>=1.0.0; extra == "realtime"'])
    sbom = _write_sbom(tmp_path, [_pkg("wave-sdk", "9.9.9")])

    result = _run_validate_sbom(str(sbom), "--target", str(target), cwd=tmp_path)

    assert result.returncode == 1
    assert "floor of 0" in result.stderr


def test_validate_sbom_usage_error_when_nothing_is_installed(tmp_path):
    empty_target = tmp_path / "sbom-env"
    empty_target.mkdir()
    sbom = _write_sbom(tmp_path, [_pkg("wave-sdk", "9.9.9")])

    result = _run_validate_sbom(str(sbom), "--target", str(empty_target), cwd=tmp_path)

    assert result.returncode == 2
    assert "expected exactly one installed wave-sdk" in result.stderr
