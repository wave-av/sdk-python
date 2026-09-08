#!/usr/bin/env python3
"""Assert the INSTALLED distribution imports, and that it did not eat `import wave`.

Run this inside the throwaway venv that `smoke-install.yml` builds, from a
directory that is not the repo checkout. It is the artifact-level half of the
stdlib-shadow guard; `tests/test_packaging.py` is the source-tree half.

WHY THIS EXISTS
---------------
`wave-sdk 2.0.0` (PyPI, 2026-04-03) shipped a top-level package named `wave`.
CPython ships `Lib/wave.py`, the standard-library WAV reader/writer. Two things
follow, and they are NOT the same bug:

  1. In a normal venv the stdlib directory precedes `site-packages` on
     `sys.path`, so the stdlib won. `import wave` returned the stdlib module and
     the SDK was unreachable under any name -- the artifact was 100%
     unimportable. Measured on the published wheel:

         $ pip install wave-sdk==2.0.0
         $ python -c "import wave_sdk"
         ModuleNotFoundError: No module named 'wave_sdk'
         $ python -c "import wave; print(wave.__file__)"
         .../lib/python3.13/wave.py          # the stdlib, not the SDK

  2. Wherever `site-packages` LEADS `sys.path` -- `pip install --target`,
     `PYTHONPATH`, AWS Lambda layers, zipapps, some vendored bundles -- the
     shipped `wave` package won instead, and then `wave.open()` was gone for
     every unrelated library in that environment that reads a WAV file. Measured
     on the same wheel:

         $ PYTHONPATH=<site-packages> python -c "import wave; wave.open('x')"
         AttributeError: module 'wave' has no attribute 'open'

Checking only the first configuration would let the second one ship, so this
script checks both: once in-process, and once in a child whose `sys.path` puts
site-packages first.

WHAT IT REFUSES TO DO
---------------------
Report success on an absent measurement. Every check is a hard failure, never a
skip: if the distribution under test is not installed, if no distribution
metadata can be enumerated, or if the child probe cannot be launched, this exits
non-zero. A guard that goes green when its input is missing is not a guard.

The stdlib check is behavioural, not just a path comparison -- it writes and
reads a real WAV frame through `wave.open()`. A module can sit at a
stdlib-looking path and still be the wrong module; a round-tripped frame cannot.

USAGE
-----
    python scripts/assert_stdlib_wave_intact.py                # dist: wave-sdk
    python scripts/assert_stdlib_wave_intact.py --dist wave-sdk --module wave_sdk

Exit 0 when every check passes, 1 otherwise.
Standard library only: it runs in a venv that holds the wheel and nothing else.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import os
import subprocess
import sys
import sysconfig
import wave
from pathlib import Path

# Names the SDK must never ship at the top level. `wave` is the one that shipped;
# the others are the near neighbours a future rename could plausibly reach for.
FORBIDDEN_TOP_LEVEL = {"wave", "audioop", "sunau", "aifc", "sndhdr", "chunk"}

_failures: list[str] = []
_checks = 0


def check(label: str, ok: bool, detail: str = "") -> bool:
    """Record one assertion. Never raises, so every check reports before exit."""
    global _checks
    _checks += 1
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    if detail:
        for line in detail.splitlines():
            print(f"          {line}")
    if not ok:
        _failures.append(label)
    return ok


def stdlib_dir() -> Path:
    return Path(sysconfig.get_paths()["stdlib"]).resolve()


def is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent)
        return True
    except ValueError:
        return False


def probe_stdlib_wave(context: str) -> None:
    """`import wave` must be CPython's WAV module -- by location, API, and behaviour."""
    resolved = Path(wave.__file__).resolve()
    std = stdlib_dir()
    under = is_under(resolved, std)

    check(
        f"[{context}] `import wave` resolves under the stdlib",
        under,
        f"resolved: {resolved}"
        if under
        else f"resolved: {resolved}\nstdlib:   {std}\n"
        "A top-level `wave` package is shadowing CPython's Lib/wave.py.",
    )

    missing = [n for n in ("open", "Error", "Wave_read", "Wave_write") if not hasattr(wave, n)]
    check(
        f"[{context}] the resolved `wave` exposes the stdlib WAV API",
        not missing,
        f"missing attributes: {missing}" if missing else "",
    )

    # Behavioural receipt: a path can lie, a round-tripped WAV frame cannot.
    try:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(8000)
            w.writeframes(b"\x00\x01")
        buf.seek(0)
        with wave.open(buf, "rb") as r:
            params = (r.getnchannels(), r.getsampwidth(), r.getframerate(), r.getnframes())
        ok, detail = params == (1, 2, 8000, 1), f"round-tripped params: {params}"
    except Exception as exc:  # noqa: BLE001 - any failure here is a real failure
        ok, detail = False, f"{type(exc).__name__}: {exc}"
    check(f"[{context}] stdlib `wave` round-trips a real WAV frame", ok, detail)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dist", default="wave-sdk", help="installed distribution name")
    ap.add_argument("--module", default="wave_sdk", help="import name the dist must provide")
    ap.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.child:
        # Re-entry with site-packages ahead of the stdlib on sys.path.
        print(f"sys.path[0:2] = {sys.path[0:2]}")
        probe_stdlib_wave("site-packages-first")
        return 1 if _failures else 0

    print(f"Interpreter : {sys.executable}")
    print(f"Working dir : {os.getcwd()}")
    print(f"Distribution: {args.dist}  ->  import {args.module}\n")

    # ---- 1. the distribution must actually be installed and importable --------
    from importlib.metadata import PackageNotFoundError, distribution, distributions

    dist = None
    with contextlib.suppress(PackageNotFoundError):
        dist = distribution(args.dist)
    check(
        f"distribution `{args.dist}` is installed in this environment",
        dist is not None,
        "" if dist else "Nothing to measure -- this is a failure, not a skip.",
    )

    mod = None
    try:
        mod = importlib.import_module(args.module)
    except Exception as exc:  # noqa: BLE001
        check(f"`import {args.module}` succeeds", False, f"{type(exc).__name__}: {exc}")
    else:
        check(f"`import {args.module}` succeeds", True, f"version {getattr(mod, '__version__', '?')}")
        check(
            f"`{args.module}` is imported from site-packages, not the stdlib",
            not is_under(Path(mod.__file__).resolve(), stdlib_dir()),
            f"resolved: {Path(mod.__file__).resolve()}",
        )

    # ---- 2. no installed distribution may claim a stdlib-shadowing top name ---
    # Scanned across EVERY installed distribution, not just ours: a dependency
    # that drops a top-level `wave` breaks the user just as thoroughly.
    seen, offenders = 0, []
    for d in distributions():
        seen += 1
        name = d.metadata["Name"] or "<unknown>"
        for f in d.files or ():
            top = str(f).split("/")[0]
            if top in FORBIDDEN_TOP_LEVEL and not top.endswith(".dist-info"):
                offenders.append(f"{name} ships top-level `{top}`")
    # Control: if the scan enumerated nothing it measured nothing, so it fails.
    check(
        "distribution scan enumerated the environment (control)",
        seen > 0,
        f"{seen} distributions scanned",
    )
    check(
        "no installed distribution ships a stdlib-shadowing top-level name",
        not offenders,
        "\n".join(sorted(set(offenders))),
    )

    # ---- 3. `import wave` is still CPython's, in the normal configuration -----
    probe_stdlib_wave("default-sys.path")

    # ---- 4. ...and in the configuration where site-packages LEADS sys.path ----
    site_dirs = [p for p in sys.path if p.endswith("site-packages") and Path(p).is_dir()]
    if not site_dirs:
        check("located site-packages for the site-packages-first probe", False,
              "Cannot run the shadowing probe -- failing rather than skipping.")
    else:
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(site_dirs + [env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
        try:
            proc = subprocess.run(
                [sys.executable, os.path.abspath(__file__), "--child",
                 "--dist", args.dist, "--module", args.module],
                env=env, capture_output=True, text=True, timeout=120, cwd=os.getcwd(),
            )
        except Exception as exc:  # noqa: BLE001
            check("site-packages-first probe ran", False, f"{type(exc).__name__}: {exc}")
        else:
            for line in proc.stdout.splitlines():
                print(f"  | {line}")
            if proc.stderr.strip():
                for line in proc.stderr.splitlines():
                    print(f"  | {line}")
            check(
                "stdlib `wave` survives with site-packages ahead of it on sys.path",
                proc.returncode == 0,
                f"child exited {proc.returncode} (PYTHONPATH={env['PYTHONPATH']})",
            )

    print(f"\n{_checks - len(_failures)}/{_checks} checks passed")
    if _failures:
        print("\nFAILED:")
        for f in _failures:
            print(f"  - {f}")
        print(
            "\nThe published artifact is broken for real users. Do not release.\n"
            "See scripts/assert_stdlib_wave_intact.py for what each check means."
        )
        return 1
    print("The installed distribution imports, and the stdlib `wave` is intact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
