# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.3.0] - not yet published (tag `v2.3.0` after merge publishes it)

This pull request bumps the version, so its notes sit under the release heading rather than
`Unreleased`.

Connectivity release. Every free flow the README documents now succeeds against the live API
with the documented `Authorization: Bearer` key (`scripts/smoke_live.py`). Billed flows reach
their route and raise the server's own payment error. The contract test now checks the request
each mapped method actually sends.

### Fixed

- **Realtime** used a host that does not resolve. `publish()`, `presence()` and `history()` now
  go through the client to `https://api.wave.online/v1/realtime/channels/{channel}/...`, so they
  raise `WaveError` on failure and send `X-Organization-Id`; the channel name is percent-encoded
  (`:` stays literal). `connect()` opens `wss://api.wave.online/v1/realtime/connect` (derived
  from `base_url`) and sends the key in the `Authorization` header on the upgrade instead of an
  `?access_token=` query parameter. A rejected upgrade raises the matching `WaveError` subclass.
  `connect()` refuses a `ws://` origin other than localhost with `ValueError`, because the key
  would travel unencrypted.
- **Inference** `complete()` posted to a proxy that rejects WAVE API keys. It now sends
  `POST /v1/inference/chat/completions` through the client. `models()` reads
  `GET /v1/inference/models` instead of requiring a registry URL and key. A 2xx without choices,
  or without a model list, raises `WaveError` with code `INVALID_RESPONSE` instead of returning
  an empty result.
- **Meter** models failed to parse every live response. `ledger()` returns the single window the
  API sends (`org`, `from`, `to`, `channels`, `generated_at`); a channel's `blocked` may be a
  count or a reason string; unknown fields are kept; a counter the response leaves out is
  `None`, never a default `0`.
- **Billed or broadcast writes added in this release are sent once**: `inference.complete()`,
  `realtime.publish()`, `voice.generate()`, `clips.detect()`, `chapters.detect()`,
  `chapters.create_chapter()`, `editor.export()`, `podcast.create()` and
  `podcast.create_episode()`. A timeout or bare 5xx after the server may have accepted the
  request is raised to the caller instead of retried, since a retry could bill a job or
  broadcast an event twice. Existing methods keep their retry behavior.
- **Error parsing** kept only the `{"error": {"code", "message"}}` shape. Flat bodies
  (`{"error": "...", "code": ..., "message": ...}`), bare `{"error": "..."}` bodies and the x402
  challenge now keep the server's code, message and context instead of becoming
  `HTTP_<status>`.
- **Retries** follow the server's `next_action`: a permanent error (for example a 503 whose
  directive is `none`, or a 429 whose directive is not a retry) is raised on the first attempt
  instead of after three backoffs. A `Retry-After` header (on a 429 or any retryable 5xx) or a
  `retry_after` directive sets the wait. A wait over 60 s is raised at once with the full value
  on the error, instead of being slept through. A `Retry-After` that is not a finite, non-negative number of seconds is
  ignored; before, `nan` or `-1` escaped as a non-`WaveError` exception.
- **Rate limits** raise `RateLimitError` from a WebSocket upgrade too, not a plain `WaveError`.
- **Inference** no longer sends the WAVE API key to `funnel_url`; the argument is ignored.
- `captions.download()` returns the caption text as `content` if the API answers with the file
  itself rather than JSON.
- **Paths** moved to the published API operations: `podcast` uses `/v1/podcast/shows` and
  `/v1/podcast/shows/{id}/episodes`; `sentiment.analyze_text()` posts to
  `/v1/sentiment/analyze`.
- **Mesh** requests carry the required `x-wave-node` header (`client.mesh.node`, or `node=` on
  any method, mutations included); a call without one, or with a multi-line node name, raises
  `ValueError` before sending. Mesh ids are encoded as one path segment, and the mutations
  (`add_peer`, `remove_peer`, `create_policy`, `trigger_failover`) are sent once rather than
  retried, so a 5xx after the server applied the change cannot fail over twice.
- **Path safety**: every request whose path contains a `.` or `..` segment raises `ValueError`
  before it is sent. httpx resolves those segments, so in 2.2.0 `clips.get("../usage")` was sent
  to `/v1/usage` with the caller's key. The methods added or changed in this release also
  encode an id as exactly one path segment (`/`, `?`, `#` and `%` are percent-encoded; `:`
  stays literal).
- Package docstring examples and the PyPI project links point at calls and pages that exist.

### Added

- `client.usage.get()`: `GET /v1/usage`, the organization's metered totals.
- `PaymentRequiredError` (HTTP 402; `accepts` and `x402_version` for an x402 challenge, spend-cap
  context in `details`) and `RouteNotServedError` (404 for a route no capability serves, or 405).
  Both subclass `WaveError`. `WaveError` gains `next_action`, `suggestions` and `doc_url`.
- `pulse.get_overview()` and `pulse.get_top_content()`; `from_`/`to` on
  `pulse.get_engagement_metrics()`.
- Methods for published operations the SDK sent to other paths: `clips.detect()`,
  `captions.download()`, `voice.generate()`, `editor.export()`, `collab.delete_room()`,
  `chapters.list_chapters()`, `chapters.create_chapter()`, `chapters.detect()`.
- `raw=True` on `WaveClient.get()` / `post()` / ... returns the `httpx.Response` for binary
  bodies.
- `scripts/smoke_live.py`: runs the documented free flows against the live API.
- `scripts/refresh_openapi_snapshot.py`: regenerates the OpenAPI snapshot the contract test
  reads.

### Deprecated

These methods and arguments warn with `DeprecationWarning`. All but two call paths the API
does not publish: `clips.detect_highlights()` (use `detect()`), `voice.synthesize()`
(`generate()`), `captions.get_text()` (`download()`), `chapters.get_default_set()`
(`list_chapters()`), `chapters.add_chapter()` (`create_chapter()`), `editor.render()`
(`export()`), `inference.profile()`, and the podcast methods with no published operation
(`get()`, `update()`, `remove()`, `get_episode()`, `publish_episode()`, `get_rss_feed()`,
`get_analytics()`, `distribute()`). The two exceptions: `collab.close_room()` is now an alias of
`delete_room()` and sends the published `DELETE`, and `InferenceAPI(funnel_url=...)` is ignored.

### Changed

- `podcast.create()` takes `name` (the API's field) as its first argument; `create_episode()`
  requires `audio_url`. Both return `PodcastShow` / `PodcastEpisode` (`Podcast` and `Episode`
  remain as aliases). The keyword `podcast_id=` is now `show_id=`. No 2.2.0 podcast call
  reached a served route, so no working call changes behavior.
- `MeterLedgerRow` is an alias of `MeterLedger`; `MeterLedger.rows` no longer exists.
- The README lists which namespaces were checked live, which wrap published operations, and
  which the API does not route today.

### Testing

- `tests/test_contract_coverage.py` calls every mapped method against a mock transport and
  asserts the verb and path it sends match the spec operation (the old test only checked that
  the method name existed). The snapshot now covers all 255 operations of the published
  document.
- `tests/test_errors.py`, `tests/test_realtime.py` and `tests/test_served_routes.py` cover the
  error envelopes, the realtime URLs and headers, and parsing of recorded live response bodies
  (`tests/fixtures/live_responses.json`, identifiers scrubbed).

## [2.2.0] - 2026-09-06

### Added

PR4-SDK: `wave.compose` (`ComposeAPI`), the Python SDK's rendering of the
WAVE Composer: `POST /v1/compose`, the shared cross-rendering (API, CLI, SDK,
MCP) contract. Types mirror the API's own `ComposeProposal` wire type field
for field via pydantic aliases, so the wire JSON stays camelCase while
Python attributes stay snake_case.

- `compose(intent, *, budget_usd=None, flow_id=None, referer=None)` -
  `POST /v1/compose` (`composer:write`). Returns a typed `ComposeProposal`:
  `stages[]`, `product_ids[]`, `tools[]`, `scopes[]`, `price_rows[]`,
  `call_shape`, `next_[]`, `executes` (always `False` - a proposal never
  executes anything), `grounding`, `grounded_at`, `manifest_hash`, `engine`,
  `flow_id`.
- `get_proposal(proposal_id)` - `GET /v1/compose/proposals/:id`
  (`composer:read`), re-reading a stored proposal instead of re-composing.
- `save_flow(proposal)` - builds the `POST /api/console/flows` body with
  `createdBy.kind: "wave-composer"` and the proposal's `manifest_hash` /
  `grounded_at`. There is no machine-auth token for `wave-composer` callers
  yet (the console's flow-save route is session-cookie only until a
  composer:write console token ships; OWED). This method never calls the
  console route and never invents a credential to do so - it prints, and
  returns, the exact `curl` a human in a signed-in console session can
  paste. Never a silent no-op.
- `wave.compose` never calls a product route: the only network calls it
  makes are `POST /v1/compose` and `GET /v1/compose/proposals/:id`.

### Testing

- `tests/test_compose.py` - a fixture round-trip test (`model_validate` ->
  `model_dump(by_alias=True)` reproduces the fixture byte-identically),
  a transport-mock test asserting `compose()` issues exactly one
  `POST /v1/compose` and no other request, and a test that `save_flow()`
  makes zero HTTP calls and returns a curl string naming
  `/api/console/flows` and `createdBy":{"kind":"wave-composer"` with no
  bearer token embedded.
- `tests/fixtures/compose_proposal.json` - a hand-built `ComposeProposal`
  fixture (a webinar-captions composition, matching the shape and sample
  values of the shared cross-rendering conformance scenario). No upstream
  engine source was copied into this repo: that reference is TS test-engine
  plumbing (a fake model door, a fake quote stub, a live-index builder) with
  no literal request/response JSON to copy verbatim, so this fixture is a
  hand-built equivalent in the same scenario rather than a byte-copy.
- Updated `tests/test_sdk_exports.py` for the new API count (43 + client)
  and version (2.2.0).

### Changed

- Bumped to 2.2.0 (additive, semver-minor): no existing method signature
  changed.

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
