"""Unit tests for scripts/ga/ga_common.py's GitHub-API authentication.

Regression under test: `fetch_json_allow_404()` called `api.github.com` with
no Authorization header, so it was subject to GitHub's unauthenticated
60-requests/hour-per-IP cap; CI runners sharing NAT'd IP pools exhausted that
quickly, got HTTP 403, and the old code turned ANY non-404 HTTPError into a
RegistryError with no detail -- which scripts/ga/ga_evidence.py then reported
as exit 2 "could not run" (an absent measurement, not a real check result).

This asserts:
  * a GITHUB_TOKEN/GH_TOKEN present in the environment IS sent as
    `Authorization: Bearer <token>` on api.github.com requests
  * that token is NEVER sent to a non-api.github.com host (e.g. pypi.org) --
    the negative control for credential scoping
  * a 403 (rate-limited, even with a token) still raises RegistryError, with
    the response body attached for diagnosis -- never silently swallowed
  * a 404 is still the normal "absent" case, unaffected by auth
No real network calls are made -- every `urllib.request.urlopen` call is
mocked.
"""
from __future__ import annotations

import io
import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ga"))

import ga_common  # noqa: E402


class _FakeCtxManager:
    def __init__(self, payload: dict, status: int = 200):
        self._payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def test_github_token_attached_to_api_github_com_requests(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_faketoken123")
    monkeypatch.delenv("GH_TOKEN", raising=False)

    captured_headers = {}

    def fake_urlopen(req, timeout=30):
        captured_headers.update(req.headers)
        return _FakeCtxManager({"name": "v2.2.0"})

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        status, body = ga_common.fetch_json_allow_404(
            "https://api.github.com/repos/wave-av/sdk-python/tags?per_page=100"
        )

    assert status == 200
    assert body == {"name": "v2.2.0"}
    # urllib.request.Request title-cases header keys ("Authorization" stays as-is).
    assert captured_headers.get("Authorization") == "Bearer ghs_faketoken123"


def test_gh_token_env_var_used_as_fallback(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GH_TOKEN", "gho_fallbacktoken")

    captured_headers = {}

    def fake_urlopen(req, timeout=30):
        captured_headers.update(req.headers)
        return _FakeCtxManager({})

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        ga_common.fetch_json_allow_404("https://api.github.com/repos/wave-av/sdk-python/tags")

    assert captured_headers.get("Authorization") == "Bearer gho_fallbacktoken"


def test_token_never_sent_to_non_github_host(monkeypatch):
    """Negative control for credential scoping: the same token present in the
    environment must NOT be attached when the request targets pypi.org."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_shouldnotleak")

    captured_headers = {}

    def fake_urlopen(req, timeout=30):
        captured_headers.update(req.headers)
        return _FakeCtxManager({"info": {"version": "2.2.0"}})

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        ga_common.fetch_json("https://pypi.org/pypi/wave-sdk/json")

    assert "Authorization" not in captured_headers


def test_no_token_in_env_means_no_auth_header(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    captured_headers = {}

    def fake_urlopen(req, timeout=30):
        captured_headers.update(req.headers)
        return _FakeCtxManager({})

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        ga_common.fetch_json_allow_404("https://api.github.com/repos/wave-av/sdk-python/tags")

    assert "Authorization" not in captured_headers


def test_403_rate_limit_raises_registry_error_with_body_not_silently_swallowed():
    """The core regression guard: a 403 (rate-limited, even with a token
    attached) must surface as a RegistryError carrying the response body --
    never as a bare, undiagnosable failure, and never coerced into looking
    like a legitimate 404 'absent' result."""

    def fake_urlopen(req, timeout=30):
        raise urllib.error.HTTPError(
            req.full_url,
            403,
            "rate limit exceeded",
            None,
            io.BytesIO(b'{"message": "API rate limit exceeded for 20.1.2.3."}'),
        )

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        pytest.raises(ga_common.RegistryError, match="rate limit exceeded"),
    ):
        ga_common.fetch_json_allow_404("https://api.github.com/repos/wave-av/sdk-python/tags")


def test_404_is_still_the_normal_absent_case():
    def fake_urlopen(req, timeout=30):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", None, io.BytesIO(b"{}"))

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        status, body = ga_common.fetch_json_allow_404(
            "https://api.github.com/repos/wave-av/sdk-python/releases/tags/v9.9.9"
        )

    assert status == 404
    assert body is None
