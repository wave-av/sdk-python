"""WAVE SDK - Mail API. Agent-facing comms surface: send, reply, search,
transcript-email, and SMS via the wave-mail-edge / gateway-proxied routes.

Sub-cent sends are x402-USDC-settled. Callers without a settled receipt receive
a 402, surfaced as a standard WaveError. Auth, scope (`mail:write` for
send/reply/sms, `mail:read` for search), entitlement, rate limit, and metering
are enforced server-side; the SDK only forwards the API key.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wave_sdk.client import WaveClient


class SendResult(BaseModel):
    message_id: str | None = None
    status: str
    amount_usdc: str | None = None


class MailSearchResult(BaseModel):
    threads: list[Any]


class SmsResult(BaseModel):
    sid: str
    status: str


class MailAPI:
    """Mail API - send, reply, search, transcript email, and SMS."""

    def __init__(self, client: WaveClient):
        self._client = client
        self._base = "/v1"

    def send(self, to: str, subject: str, text: str | None = None, html: str | None = None, inbox_id: str | None = None) -> SendResult:
        """Send an email. Sub-cent sends are x402-USDC-settled; without a settled
        receipt the server returns 402."""
        body = {"to": to, "subject": subject, "text": text, "html": html, "inbox_id": inbox_id}
        return SendResult(**self._client.post(f"{self._base}/mail/send", json={k: v for k, v in body.items() if v is not None}))

    def reply(self, message_id: str, text: str | None = None, html: str | None = None, reply_all: bool | None = None) -> SendResult:
        """Reply to an existing message by its `message_id`."""
        body = {"text": text, "html": html, "reply_all": reply_all}
        return SendResult(**self._client.post(f"{self._base}/mail/reply/{message_id}", json={k: v for k, v in body.items() if v is not None}))

    def search(self, q: str) -> MailSearchResult:
        """Full-text search across mail threads."""
        return MailSearchResult(**self._client.get(f"{self._base}/mail/search", params={"q": q}))

    def transcript_email(self, to: str, transcript: str, title: str | None = None) -> SendResult:
        """Send a transcript email (the comms productization surface)."""
        body = {"to": to, "transcript": transcript, "title": title}
        return SendResult(**self._client.post(f"{self._base}/transcripts/email", json={k: v for k, v in body.items() if v is not None}))

    def sms(self, to: str, body: str) -> SmsResult:
        """Send an SMS message."""
        return SmsResult(**self._client.post(f"{self._base}/sms/send", json={"to": to, "body": body}))
