"""
Packaging / distribution-metadata guards.

These tests exist because of a class of defect that NO other gate in this repo
caught, and that only becomes visible once the package is on PyPI — where it is
unfixable, since PyPI refuses a re-upload of an already-published version.

The published `wave-sdk==2.0.0` sdist/wheel installs a top-level package named
`wave`. CPython's standard library ships `Lib/wave.py` (WAV audio I/O), and the
stdlib directory sits AHEAD of `site-packages` on `sys.path`. So `import wave`
in a fresh install of 2.0.0 resolves to the stdlib module and the entire SDK is
unreachable — the artifact is 100% unimportable, on every Python version. The
repo checkout hid it: the checkout directory is first on `sys.path`, so the
local `wave/` package won `import wave` during development and under pytest.

`.github/workflows/smoke-install.yml` guards the same class at the wheel level
(build -> fresh venv -> install -> import from elsewhere). These tests are the
cheap, always-on half: they fail at PR time, in the normal unit run, before a
wheel is ever built, and they extend the guard to the two metadata fields that
a wheel build cannot self-check — the license and the version.

Guarded here:
  1. No top-level package this repo ships may shadow a stdlib module name.
  2. `import wave` must still resolve to the stdlib, from inside the checkout.
  3. `wave_sdk.__version__` must equal `[project] version` in pyproject.toml.
  4. `[project] license` must match the license the LICENSE file actually is.
"""

import re
import sys
import sysconfig
from pathlib import Path

import pytest

try:  # tomllib is stdlib from 3.11; `tomli` is a dev dependency below that.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on 3.9/3.10 only
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _pyproject() -> dict:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def _stdlib_top_level_names() -> set:
    """Every name `import <name>` could resolve to from the standard library.

    `sys.stdlib_module_names` is 3.10+, so on 3.9 fall back to reading the
    stdlib directory. Both paths are unioned so the guard never gets weaker on
    a newer interpreter than the one that wrote it.
    """
    names = set(sys.builtin_module_names)
    names |= set(getattr(sys, "stdlib_module_names", ()))
    stdlib_dir = Path(sysconfig.get_paths()["stdlib"])
    if stdlib_dir.is_dir():
        for entry in stdlib_dir.iterdir():
            if entry.suffix == ".py":
                names.add(entry.stem)
            elif entry.is_dir() and (entry / "__init__.py").exists():
                names.add(entry.name)
    return names


def _shipped_top_level_packages() -> list:
    """Top-level importable packages in the checkout that setuptools will ship.

    Derived from the filesystem (any root-level directory with an `__init__.py`)
    rather than from the pyproject include-globs, because the failure mode being
    guarded is exactly someone re-adding a directory the globs would sweep up.
    `tests` is excluded: it is not in `[tool.setuptools.packages.find] include`,
    so it is never part of the distribution.
    """
    skip = {"tests"}
    return sorted(
        p.name
        for p in REPO_ROOT.iterdir()
        if p.is_dir()
        and not p.name.startswith((".", "_"))
        and p.name not in skip
        and (p / "__init__.py").exists()
    )


def test_repo_ships_the_wave_sdk_package():
    """Control for the two shadow tests below: prove the scan sees anything at all.

    Without this, a bug that made `_shipped_top_level_packages()` return `[]`
    would turn the shadow guard into a test that can never fail.
    """
    assert "wave_sdk" in _shipped_top_level_packages()


def test_no_shipped_package_shadows_a_stdlib_module():
    """A distribution package named after a stdlib module is permanently unimportable.

    site-packages is AFTER the stdlib on sys.path, so the stdlib always wins.
    """
    stdlib = _stdlib_top_level_names()
    collisions = [name for name in _shipped_top_level_packages() if name in stdlib]
    assert collisions == [], (
        f"top-level package(s) {collisions} collide with a Python standard-library "
        f"module name. The stdlib precedes site-packages on sys.path, so a user who "
        f"runs `pip install wave-sdk` could never import them. Rename the package "
        f"(this is exactly the defect that shipped as wave-sdk 2.0.0's `wave`)."
    )


def test_import_wave_still_resolves_to_the_standard_library():
    """The specific regression: re-adding a top-level `wave/` here would break users.

    Run from the repo checkout, the checkout is first on sys.path — so if a
    `wave/` package reappears, this assertion fails HERE, which is the one place
    the old bug was invisible.
    """
    import wave  # noqa: F401 - imported for its resolved location, not its API

    stdlib_dir = Path(sysconfig.get_paths()["stdlib"]).resolve()
    resolved = Path(wave.__file__).resolve()
    assert stdlib_dir in resolved.parents, (
        f"`import wave` resolved to {resolved}, not the standard library at "
        f"{stdlib_dir}. A top-level `wave` package has been reintroduced."
    )
    assert REPO_ROOT not in resolved.parents, f"`import wave` resolved into this repo: {resolved}"


def test_dunder_version_matches_pyproject_version():
    """`wave_sdk.__version__` is what users print; pyproject is what PyPI records.

    `.github/workflows/release.yml` checks the git TAG against pyproject, but it
    does so on the publish job — and its `__version__` assertion runs only AFTER
    the irreversible upload. This check runs on every pull request instead.
    """
    import wave_sdk

    assert wave_sdk.__version__ == _pyproject()["project"]["version"]


def test_distribution_name_is_wave_sdk():
    """`pip install wave-sdk` is what README, CHANGELOG and MIGRATING all promise."""
    assert _pyproject()["project"]["name"] == "wave-sdk"


def test_declared_license_matches_the_license_file():
    """Shipped metadata must not contradict the LICENSE bundled beside it.

    A wheel built before this guard carried `License: MIT` and
    `Classifier: License :: OSI Approved :: MIT License` in dist-info/METADATA
    while dist-info/licenses/LICENSE was the Apache 2.0 text — two different
    grants in one artifact. LICENSE + NOTICE are the authoritative pair, so
    pyproject is asserted against them, never the reverse.
    """
    license_text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
    first_lines = "\n".join(license_text.splitlines()[:5])
    assert "Apache License" in first_lines and "Version 2.0" in first_lines, (
        "LICENSE is no longer Apache-2.0; update this guard and pyproject together."
    )

    project = _pyproject()["project"]
    assert project["license"] == {"text": "Apache-2.0"}, (
        f"[project] license is {project['license']!r} but LICENSE is Apache-2.0"
    )

    license_classifiers = [c for c in project["classifiers"] if c.startswith("License ::")]
    assert license_classifiers == ["License :: OSI Approved :: Apache Software License"], (
        f"license classifier(s) {license_classifiers} contradict the Apache-2.0 LICENSE file"
    )


def test_notice_file_is_shipped_alongside_the_license():
    """Apache-2.0 section 4(d): a NOTICE file must travel with the distribution.

    setuptools>=69 auto-includes root LICENSE* and NOTICE* into
    `dist-info/licenses/`. This asserts the file still exists and still carries
    the trademark carve-out, so it cannot be silently dropped.
    """
    notice = (REPO_ROOT / "NOTICE").read_text(encoding="utf-8")
    assert "WAVE Online, LLC" in notice
    assert "trademark" in notice.lower()


@pytest.mark.parametrize("doc", ["README.md", "MIGRATING.md"])
def test_docs_do_not_tell_users_to_import_wave(doc):
    """No shipped doc may hand a user `import wave` / `from wave import ...`.

    README 2.0.0 documented `from wave import Wave`, which is precisely the line
    that raised ImportError for every installed user.
    """
    text = (REPO_ROOT / doc).read_text(encoding="utf-8")
    offenders = [
        line.strip()
        for line in text.splitlines()
        # `wave_sdk` / `wave_av_sdk` must not trip this; a bare `wave` and a
        # submodule path like `from wave.realtime import ...` both must.
        if re.match(r"^\s*(import\s+wave|from\s+wave)(?!\w)", line)
    ]
    assert offenders == [], f"{doc} instructs users to import the stdlib `wave`: {offenders}"
