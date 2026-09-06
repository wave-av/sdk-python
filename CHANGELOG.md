# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.1.0] - 2026-09-01 (not yet published to PyPI)

### Fixed

- **Critical**: the top-level installable package was named `wave`, which
  collides with the Python standard library's own `wave` module (WAV audio
  I/O, `Lib/wave.py`, present in every CPython install). Because the stdlib
  is earlier on `sys.path` than `site-packages`, a fresh `pip install
  wave-sdk` followed by the README's own `from wave import Wave` resolved
  to the STDLIB module and raised `ImportError: cannot import name 'Wave'
  from 'wave'` — on every supported Python version, in every environment
  except the SDK's own repo checkout (where the checkout directory being
  first on `sys.path` masked the collision during development and in the
  test suite). Verified live against the published 2.0.0 wheel from PyPI in
  two isolated interpreters (3.14, 3.12); see the accompanying PR's LIVE
  RECEIPTS. The installable package is renamed `wave_sdk` (`pip install
  wave-sdk` still works; `from wave_sdk import Wave` now actually resolves
  to the SDK). This does not change the 2.0.0 contract on PyPI — 2.0.0 was
  never fixable in place and 2.1.0 has not shipped yet, so this lands before
  the collision reaches a published release.

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
- `tests/test_readme_quickstart.py` - asserts every `client.<namespace>.<method>`
  call in the README's quickstart resolves to a real SDK method.
- Updated `tests/test_sdk_exports.py` for the new API count (42 + client)
  and version (2.1.0).

### Changed

- Bumped to 2.1.0 (additive, semver-minor): no existing method signature
  changed.

## [2.0.0] - 2026-04-03

Initial public release of the WAVE Python SDK on PyPI as `wave-sdk`: 35 `*API`
classes covering streaming, production, analytics, and content workflows
(verified against the published wheel's `wave/__init__.py`; the PyPI package
`Summary` metadata for this release says "33 API modules", which undercounts
by 2 — a pre-existing metadata typo baked into the immutable 2.0.0 upload,
noted here rather than fixed retroactively since PyPI release metadata for a
published version cannot be edited).
