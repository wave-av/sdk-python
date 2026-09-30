# WAVE SDK for Python

Media infrastructure for the agentic internet. Official Python SDK for WAVE, by
WAVE Online, LLC.

## Installation

```bash
pip install wave-sdk
# with the realtime WebSocket client:
pip install 'wave-sdk[realtime]'
```

The distribution is `wave-sdk` and the import is `wave_sdk`. No other distribution name is
published for this SDK.

## Quick start

Every call goes to `https://api.wave.online` with your API key in an
`Authorization: Bearer` header.

```python
import os

from wave_sdk import Wave

client = Wave(api_key=os.environ["WAVE_API_KEY"])

# Your organization's metered usage. Nothing has to exist first, so it is the
# quickest check that a key works.
usage = client.usage.get()
print(usage.org, usage.range.days)

# Search your organization's indexed media
results = client.search.search(query="product launch")

# List your org's published pricing tiers (requires the pricing:read scope)
manifests = client.pricing.list_manifests()

# Propose a plan across WAVE products for a plain-English intent (requires
# composer:write). A proposal never executes anything.
proposal = client.compose.compose("live captions for tomorrow's webinar")
print(proposal.stages, proposal.price_rows, proposal.executes)  # executes is always False
```

Media jobs are billed. An organization without a payment method gets a
`PaymentRequiredError` (HTTP 402) whose message says what to add:

```python
transcription = client.transcribe.create(source_url="https://example.com/clip.mp4")
captions = client.captions.generate(media_id=transcription.id, media_type="video")
```

`scripts/smoke_live.py` runs the free flows above, and the realtime and inference ones below,
against the live API: `WAVE_API_KEY=... python3 scripts/smoke_live.py`.

## Namespaces

`client.<namespace>` attributes of the `Wave` facade. Every method raises a `WaveError`
subclass carrying the server's own error code and message when a call fails (see
[Error handling](#error-handling)).

### Checked against the live API in this release

| Namespace          | What it does                                                                 |
| ------------------ | ---------------------------------------------------------------------------- |
| `client.usage`     | `get()`: the organization's metered totals (`GET /v1/usage`)                |
| `client.search`    | `search()`, `get_analytics()`                                                |
| `client.pricing`   | `list_manifests()`: seller tier manifests (`pricing:read`)                   |
| `client.compose`   | `compose()`: propose a plan across products; never executes                 |
| `client.pulse`     | `get_overview()`, `get_top_content()`, `get_engagement_metrics()`            |
| `client.meter`     | `ledger()`, `rollup()`: usage per comms channel (`meter:read`)              |
| `client.realtime`  | `presence()`, `history()`, `connect()` over WebSocket; `publish()` needs `realtime:write` |
| `client.inference` | `models()` and `complete()`, OpenAI-compatible, with your WAVE key           |
| `client.mesh`      | `list_peers()` for a mesh node (set `client.mesh.node` first)                |

### Wrapping published API operations

The request each of these methods sends is checked against the
[published OpenAPI document](https://api.wave.online/openapi.json) by
`tests/test_contract_coverage.py`.

| Namespace           | Published operations it wraps                                      |
| ------------------- | ------------------------------------------------------------------ |
| `client.clips`      | list, create, get, update, remove, `detect()`                      |
| `client.captions`   | list, `generate()`, get, remove, `download()`                      |
| `client.transcribe` | list, create, get, remove                                          |
| `client.voice`      | `list_voices()`, `clone_voice()`, `generate()`                     |
| `client.editor`     | project CRUD, `export()`                                           |
| `client.collab`     | rooms: list, create, get, `delete_room()`                          |
| `client.chapters`   | `list_chapters()`, `create_chapter()`, `detect()` for a video      |
| `client.studio`     | productions: list, create, get                                     |
| `client.phone`      | calls: `list_calls()`, `make_call()`                               |
| `client.sentiment`  | `analyze()`, `analyze_text()`, `list()`                            |
| `client.podcast`    | shows and episodes: `list()`, `create()`, `list_episodes()`, `create_episode()` |
| `client.pipeline`   | streams: list, create, get, start, stop                            |

At the time of this release the API answers `404` for the published streams and podcast-shows
operations and `405` for `GET /v1/sentiment`; those calls raise `RouteNotServedError` until the
API serves them.

### Other namespaces

`fleet`, `ghost`, `edge`, `zoom`, `scene`, `vault`, `connect`, `studio_ai`, `perception`,
`transcripts`, and the methods of the namespaces above that are not listed, call endpoints
outside the published API reference.

`prism`, `marketplace`, `distribution`, `desktop`, `signage`, `qr`, `audience`, `creator`,
`slides`, `usb`, `notifications`, `drm` and `mail` are not routed by the API today: every call
raises `RouteNotServedError` with code `ROUTE_NOT_MAPPED`. They stay in the SDK so existing code
keeps importing. The error's `doc_url` points at the API's capability index.

## Realtime

```python
channel = client.realtime.connect("stream:abc")   # wss://api.wave.online/v1/realtime/connect
channel.on("caption.cue", lambda data: print(data))
channel.run()                                      # blocks, dispatching frames

client.realtime.presence("stream:abc")             # {"channel": ..., "members": [...]}
client.realtime.history("stream:abc", limit=20)
```

The key travels in the `Authorization` header on the WebSocket upgrade too, never in the URL.
A rejected upgrade raises the same `WaveError` subclass a REST call would.

## Inference

```python
models = client.inference.models()                 # GET /v1/inference/models
reply = client.inference.complete(models[0].id, [{"role": "user", "content": "hi"}], max_tokens=64)
print(reply.content)
```

`complete()` sends `POST /v1/inference/chat/completions` and needs the `dispatch:write` scope.

## Mesh

Every `/v1/mesh` request names the node it is for in an `x-wave-node` header:

```python
client.mesh.node = "studio-a"
peers = client.mesh.list_peers()                   # {"org", "count", "peers": [...]}
peers_b = client.mesh.list_peers(node="studio-b")  # any method takes node= for one call
```

Every mesh method, mutations included, raises `ValueError` before sending when no node is set.
The mutations (`add_peer`, `remove_peer`, `create_policy`, `trigger_failover`) are sent once and
never retried automatically.

## Error handling

```python
from wave_sdk import PaymentRequiredError, RateLimitError, RouteNotServedError, WaveError

try:
    client.clips.get("invalid-id")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except PaymentRequiredError as e:
    # A plan spend cap (e.code == "SPEND_CAP_TIER_BLOCKED", context in e.details) or an x402
    # payment challenge (payment options in e.accepts).
    print(f"{e.code}: {e.message}")
except RouteNotServedError as e:
    print(f"Not served: {e.code} (capability index: {e.doc_url})")
except WaveError as e:
    print(f"{e.code}: {e.message} ({e.status_code}, request {e.request_id})")
```

`WaveError` carries `code`, `message`, `status_code`, `request_id`, `details` (for example
`available_scopes` on a 403), `suggestions`, `doc_url` and `next_action`. The client retries a
failed request only when a retry can help: a 429, a 5xx without a directive, or a
`next_action` of `retry_backoff` / `retry_after`. A permanent error such as an unconfigured
server-side store is raised on the first attempt.

## Requirements

- Python 3.9+
- httpx
- pydantic
- `websocket-client` for `realtime.connect()` (the `realtime` extra)

## Migrating

2.3.0 moves several methods onto the paths the API publishes. The old names still work and
emit a `DeprecationWarning`; see
[MIGRATING.md](https://github.com/wave-av/sdk-python/blob/main/MIGRATING.md).

If you installed `wave-av-sdk` or `wave-sdk` at `2.0.0`, two names changed:

- **Install** `wave-sdk` (not `wave-av-sdk`).
- **Import** `wave_sdk` (not `wave`).

```diff
-from wave import Wave
+from wave_sdk import Wave
```

The old `wave` package collided with the Python standard library's own `wave` module and was
never importable from an installed `2.0.0`; the uninstall step and a bulk find-and-replace are
in [MIGRATING.md](https://github.com/wave-av/sdk-python/blob/main/MIGRATING.md).

## License

Apache-2.0 - WAVE Online, LLC. See
[LICENSE](https://github.com/wave-av/sdk-python/blob/main/LICENSE) and
[NOTICE](https://github.com/wave-av/sdk-python/blob/main/NOTICE); the WAVE marks are not
licensed under the Apache grant.
