# Migrating to `wave-sdk` 2.1.0

Two things changed between the published `2.0.0` releases and `2.1.0`: the
**distribution you install** and the **package you import**. Both changes are
mechanical, and the second one is not optional — the old import never worked
outside the SDK's own repo.

| | Old (`2.0.0`, published) | New (`2.1.0`) |
| --- | --- | --- |
| Install name(s) | `wave-av-sdk`, `wave-sdk` | `wave-sdk` |
| Import name | `wave` (broken — see below) | `wave_sdk` |
| Client class | `Wave` | `Wave` (unchanged) |
| Method surface | 35 `*API` classes | 42 `*API` classes |

## 1. Install `wave-sdk`

```bash
pip uninstall -y wave-av-sdk wave-sdk
pip install "wave-sdk>=2.1.0"
```

`wave-av-sdk` and `wave-sdk` were both published at `2.0.0` and contain the same
code. `wave-sdk` is the one name that continues; `wave-av-sdk` is not being
republished. Uninstall **both** before installing: they each drop a top-level
`wave/` directory into `site-packages`, and leaving one behind leaves that
directory (and its stale `2.0.0` modules) on disk next to the new `wave_sdk`.

## 2. Change `import wave` to `import wave_sdk`

```diff
-from wave import Wave
+from wave_sdk import Wave

-from wave import WaveError, RateLimitError
+from wave_sdk import WaveError, RateLimitError

-import wave
-client = wave.Wave(api_key=..., organization_id=...)
+import wave_sdk
+client = wave_sdk.Wave(api_key=..., organization_id=...)
```

Nothing below the top-level name changed. Every class, method, argument and
return type keeps its name, so a find-and-replace of the import line is the
whole migration:

```bash
# from the root of your project
grep -rl --include='*.py' -E '^\s*(from|import)\s+wave(\W|$)' . \
  | xargs sed -i.bak -E 's/^(\s*)(from|import)(\s+)wave(\W|$)/\1\2\3wave_sdk\4/'
```

## Why the rename was required

CPython ships a standard-library module called `wave` (`Lib/wave.py`, the WAV
audio reader/writer) in every install, on every supported version. The
standard-library directory sits **ahead of `site-packages`** on `sys.path`.

So for anyone who ran `pip install wave-sdk==2.0.0`, `import wave` resolved to
the standard library, not to the SDK. The SDK's own files were on disk, in
`site-packages/wave/`, and were unreachable:

```console
$ python -m venv v && ./v/bin/pip install wave-sdk==2.0.0
$ ./v/bin/python -c "import wave; print(wave.__file__)"
/…/lib/python3.12/wave.py            # the standard library, not the SDK
$ ./v/bin/python -c "from wave import Wave"
ImportError: cannot import name 'Wave' from 'wave'
```

The defect was invisible during development because the repo checkout is the
first entry on `sys.path`; inside the checkout, the local `wave/` directory won
`import wave` and the test suite passed. `wave_sdk` collides with nothing, and
`import wave` now correctly keeps meaning the standard library:

```console
$ ./v/bin/python -c "import wave_sdk; print(wave_sdk.__version__)"
2.1.0
$ ./v/bin/python -c "import wave; print(wave.__file__)"
/…/lib/python3.12/wave.py            # still the standard library — no shadowing
```

Two gates keep this from recurring: `tests/test_packaging.py` fails any pull
request that reintroduces a top-level package named after a standard-library
module, and `.github/workflows/smoke-install.yml` builds the wheel and imports
it from a fresh virtualenv with no repo on `sys.path`.

## A note on the `wave.<api>` names in the README

The README's API tables are written as `wave.clips`, `wave.pipeline`, and so on.
Those are **attributes of a client instance**, not module paths — they describe
the shape of the `Wave` facade whatever you name your variable:

```python
from wave_sdk import Wave

wave = Wave(api_key="…", organization_id="org_123")
wave.clips.list()        # the `wave.clips` in the README table
```

There is no importable `wave` module in this SDK, and there will not be one.

## License

`2.1.0` also corrects the distribution's license metadata. The repo has been
Apache-2.0 since commit `99d81d3`, but `pyproject.toml` still declared `MIT`, so
`2.0.0` shipped `License: MIT` in its `METADATA` alongside an Apache-2.0
`LICENSE` file in the same archive. The license itself did not change — the
metadata now matches the `LICENSE` and `NOTICE` files it ships with.
