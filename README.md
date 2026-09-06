# WAVE SDK for Python

Media infrastructure for the agentic internet. Official Python SDK for WAVE, by
WAVE Online, LLC.

## Installation

```bash
pip install wave-sdk
```

## Quick start

```python
from wave_sdk import Wave

client = Wave(api_key="your-api-key", organization_id="org_123")

# Search your organization's indexed media
results = client.search.search(query="product launch")

# List your org's published pricing tiers (requires the pricing:read scope)
manifests = client.pricing.list_manifests()

# Transcribe a recording and auto-generate captions for it
transcription = client.transcribe.create(source_url="https://example.com/clip.mp4")
captions = client.captions.generate(media_id=transcription.id, media_type="video")
```

## All 42 APIs

### P1 - Core

| API             | Description             |
| --------------- | ----------------------- |
| `wave.pipeline` | Live streaming engine   |
| `wave.studio`   | Multi-camera production |

### P2 - Enterprise

| API          | Description             |
| ------------ | ----------------------- |
| `wave.fleet` | Device fleet management |
| `wave.ghost` | AI auto-directing       |
| `wave.mesh`  | Multi-region failover   |
| `wave.edge`  | CDN and edge workers    |
| `wave.pulse` | Analytics and BI        |
| `wave.prism` | Virtual Device Bridge   |
| `wave.zoom`  | Zoom integration        |

### P3 - Content & Commerce

| API                 | Description        |
| ------------------- | ------------------ |
| `wave.clips`        | Video clips        |
| `wave.editor`       | Video editor       |
| `wave.voice`        | Voice synthesis    |
| `wave.phone`        | Phone calls        |
| `wave.collab`       | Collaboration      |
| `wave.captions`     | Auto-captions      |
| `wave.chapters`     | Video chapters     |
| `wave.studio_ai`    | AI assistant       |
| `wave.transcribe`   | Transcription      |
| `wave.sentiment`    | Sentiment analysis |
| `wave.search`       | Content search     |
| `wave.scene`        | Scene detection    |
| `wave.vault`        | Recording storage  |
| `wave.marketplace`  | Marketplace        |
| `wave.connect`      | Integrations       |
| `wave.distribution` | Social simulcast   |
| `wave.desktop`      | Desktop Node       |
| `wave.signage`      | Digital signage    |
| `wave.qr`           | QR codes           |
| `wave.audience`     | Polls/Q&A          |
| `wave.creator`      | Monetization       |

### P4 - Specialized

| API            | Description        |
| -------------- | ------------------ |
| `wave.podcast` | Podcast production |
| `wave.slides`  | Slides-to-video    |
| `wave.usb`     | USB relay          |

### Cross-cutting

| API                  | Description                                    |
| -------------------- | ----------------------------------------------- |
| `wave.notifications` | User notifications, preferences, delivery       |
| `wave.drm`           | Digital rights management                       |
| `wave.realtime`      | Live control and event plane (WebSocket)        |

### Agent-native and comms productization (2.1.0)

| API                | Description                                                  |
| ------------------ | ------------------------------------------------------------ |
| `wave.transcripts` | The voice-agent transcript (list + read)                     |
| `wave.mail`        | Send, reply, search, transcript email, and SMS               |
| `wave.meter`       | Read-only usage ledger and rollup (`meter:read`)              |
| `wave.pricing`     | The seller tier-manifest registry (`pricing:read`/`:write`)   |
| `wave.perception`  | Agentic live-media `subscribe()` control plane                |
| `wave.inference`   | One completion endpoint through the measured funnel           |

## Error handling

```python
from wave_sdk import WaveError, RateLimitError

try:
    client.clips.get("invalid-id")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except WaveError as e:
    print(f"{e.code}: {e.message} ({e.status_code})")
```

## Requirements

- Python 3.9+
- httpx
- pydantic

## Migrating from 2.0.0

If you installed `wave-av-sdk` or `wave-sdk` at `2.0.0`, two names changed:

- **Install** `wave-sdk` (not `wave-av-sdk`).
- **Import** `wave_sdk` (not `wave`).

```diff
-from wave import Wave
+from wave_sdk import Wave
```

Nothing below the top-level name changed, so replacing the import line is the
whole migration. The old `wave` package collided with the Python standard
library's own `wave` module and was never importable from an installed
`2.0.0` — full detail, the uninstall step, and a bulk find-and-replace are in
[MIGRATING.md](MIGRATING.md).

Note that the `wave.<api>` names in the tables above are attributes of a client
instance, not module paths: name your client whatever you like
(`client = Wave(...)` in the quick start above), and `client.clips` is the row
the table writes as `wave.clips`.

## License

Apache-2.0 - WAVE Online, LLC. See [LICENSE](LICENSE) and [NOTICE](NOTICE); the
WAVE marks are not licensed under the Apache grant.
