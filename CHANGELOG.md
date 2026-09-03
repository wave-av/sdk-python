# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [3.0.0] - 2026-09-03

### Fixed

- **P0: the package was permanently unimportable exactly as documented.** The published
  `wave-sdk` / `wave-av-sdk` distribution installs a top-level module named `wave`, which
  collides with Python's own standard-library `wave` module (WAV audio file I/O, present in
  every CPython install since 2.x). The stdlib is always resolved before `site-packages`, so
  `from wave import Wave` — the exact line in this README's own "Quick start" — has never
  worked on a fresh install, on any Python version, on any platform:
  `ImportError: cannot import name 'Wave' from 'wave' (.../lib/python3.14/wave.py)`.
  Live-verified 2026-09-03 with a clean `uv venv` + `pip install wave-sdk` (installs `2.0.0`)
  running the documented quick-start line.

### Changed

- **BREAKING: the importable package is renamed `wave` -> `wave_sdk`.** The PyPI distribution
  name is unchanged (still `pip install wave-sdk`); every import changes from
  `from wave import ...` / `from wave.<module> import ...` to `from wave_sdk import ...` /
  `from wave_sdk.<module> import ...`. This is the only viable fix — the stdlib module cannot
  be renamed or unregistered, and shadowing it silently would leave every consumer's own
  `import wave` (e.g. anything touching WAV files) broken instead. Major version bump per
  semver; there is no migration path that preserves the old import path, because the old
  import path never actually reached this package.

## [2.1.0] - 2026-09-01

### Added

TS-namespace parity: the six `@wave-av/sdk` (TypeScript, 2.1.2, 42 Wave-facade
namespaces) modules that had no Python counterpart are now implemented,
bringing the Python SDK from 35 `*API` classes (the published 2.0.0 baseline)
to 42, matching the TS facade 1:1.

- `wave.transcripts` (`TranscriptAPI`) - read-only access to the voice-agent
  transcript (list + read) persisted by the realtime plane.
- `wave.mail` (`MailAPI`) - send, reply, search, transcript-email, and SMS
  over the mail-edge / gateway-proxied routes (`mail:read`/`mail:write`).
- `wave.meter` (`MeterAPI`) - read-only usage ledger and rollup aggregates
  for the comms productization planes (`meter:read`).
- `wave.pricing` (`PricingAPI`) - the seller tier-manifest registry: create,
  list, and read pricing manifests (`pricing:read`/`pricing:write`).
- `wave.perception` (`PerceptionAPI`) - the agentic live-media `subscribe()`
  control plane: attach an agent to any live stream (WHEP/SRT/Cloudflare
  Stream) and get back a receive descriptor plus the meters it bills on.
- `wave.inference` (`InferenceAPI`) - one completion call through the
  measured funnel (`inference.wave.online`), plus registry reads (model
  catalog, measured floor/ceiling profile) when a registry endpoint and key
  are supplied.

### Testing

- `tests/test_parity_apis.py` - mocked-HTTP unit tests for all six new
  classes (request shape, response parsing, error paths).
- `tests/test_contract_coverage.py` - a contract test asserting every
  operation in a snapshot of the live WAVE OpenAPI spec
  (`https://api.wave.online/openapi.json`, 75 ops / 54 paths, fetched
  2026-09-01) has a corresponding Python method, or is in a justified
  allowlist (new backend surfaces neither SDK wraps yet, or pre-existing
  studio-ai drift that predates this release).
- `tests/test_readme_quickstart.py` - asserts every `wave.<namespace>.<method>`
  call in the README's quickstart resolves to a real SDK method.
- Updated `tests/test_sdk_exports.py` for the new API count (42 + client)
  and version (2.1.0).

### Changed

- Bumped to 2.1.0 (additive, semver-minor): no existing method signature
  changed.
