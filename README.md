# WAVE SDK for Python

Official Python SDK for the WAVE API by WAVE Inc.

## Installation

```bash
pip install wave-sdk
```

## Quick start

```python
from wave import Wave

wave = Wave(api_key="your-api-key", organization_id="org_123")

# Create and start a live stream
stream = wave.pipeline.create(title="My Stream", protocol="webrtc")
wave.pipeline.start(stream.id)
health = wave.pipeline.get_health(stream.id)
print(f"Viewers: {health['viewer_count']}")

# Create a virtual camera from NDI
device = wave.prism.create_device(
    name="PTZ Camera 1",
    type="camera",
    source_protocol="ndi",
    source_endpoint="NDI-CAM-1",
    node_id="node_abc",
    ptz_enabled=True,
)

# Get analytics
viewers = wave.pulse.get_viewer_analytics(time_range="24h")
```

## All 33 APIs

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

## Error handling

```python
from wave import WaveError, RateLimitError

try:
    wave.pipeline.get("invalid-id")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except WaveError as e:
    print(f"{e.code}: {e.message} ({e.status_code})")
```

## Requirements

- Python 3.9+
- httpx
- pydantic

## License

MIT - WAVE Inc.
