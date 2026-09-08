"""Unit tests for scripts/release/check_drift.py's `pypi_attestations()`.

Regression under test: the function used to read the legacy PyPI JSON API
(`https://pypi.org/pypi/<project>/<version>/json`), whose `urls[].provenance`
field is permanently null on PyPI today -- so a package with real, published
PEP 740 attestations was reported as having NONE. It now reads the PyPI
Simple API's per-file `provenance` link and confirms it resolves via the
PyPI Integrity API. No network calls are made in this test file -- every
`urllib.request.urlopen` call is mocked with fixture JSON.
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
sys.path.insert(0, str(REPO_ROOT / "scripts" / "release"))

import check_drift  # noqa: E402


class _FakeCtxManager:
    """Mimics the object returned by urllib.request.urlopen used as a context manager."""

    def __init__(self, payload: dict, status: int = 200):
        self._payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


SIMPLE_INDEX_BOTH_PRESENT = {
    "meta": {"api-version": "1.1"},
    "name": "wave-sdk",
    "files": [
        {
            "filename": "wave_sdk-2.2.0-py3-none-any.whl",
            "url": "https://files.pythonhosted.org/.../wave_sdk-2.2.0-py3-none-any.whl",
            "provenance": "https://pypi.org/integrity/wave-sdk/2.2.0/wave_sdk-2.2.0-py3-none-any.whl/provenance",
        },
        {
            "filename": "wave_sdk-2.2.0.tar.gz",
            "url": "https://files.pythonhosted.org/.../wave_sdk-2.2.0.tar.gz",
            "provenance": "https://pypi.org/integrity/wave-sdk/2.2.0/wave_sdk-2.2.0.tar.gz/provenance",
        },
        # A different, older version's file -- must NOT be picked up when checking 2.2.0.
        {
            "filename": "wave_sdk-2.1.0-py3-none-any.whl",
            "url": "https://files.pythonhosted.org/.../wave_sdk-2.1.0-py3-none-any.whl",
            "provenance": None,
        },
    ],
    "versions": ["2.1.0", "2.2.0"],
}

INTEGRITY_BUNDLE_PRESENT = {
    "version": "2.2.0",
    "attestation_bundles": [{"attestations": [{"envelope": {"statement": "..."}}]}],
}


def test_attestations_present_via_simple_api_and_integrity_api():
    """The real-world regression case: PyPI's legacy JSON says nothing (it
    always does), but the Simple API + Integrity API say provenance IS
    present for wave-sdk 2.2.0 -- the function must report `any_attested`."""

    def fake_urlopen(req, timeout=20):
        url = req.full_url
        if "pypi.org/simple/wave-sdk" in url:
            assert req.headers.get("Accept") == check_drift.SIMPLE_INDEX_ACCEPT
            return _FakeCtxManager(SIMPLE_INDEX_BOTH_PRESENT)
        if "pypi.org/integrity/wave-sdk/2.2.0/" in url:
            return _FakeCtxManager(INTEGRITY_BUNDLE_PRESENT)
        raise AssertionError(f"unexpected URL fetched: {url}")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        attested, missing = check_drift.pypi_attestations("2.2.0")

    assert attested is True
    assert missing == []


def test_attestations_genuinely_absent_is_not_an_unreadable_error():
    """Negative control: PyPI Integrity API returning 404 for every file is a
    real, meaningful "no provenance" finding -- report it as missing, do NOT
    raise UnreadableError (a 404 here is not a read failure)."""

    def fake_urlopen(req, timeout=20):
        url = req.full_url
        if "pypi.org/simple/wave-sdk" in url:
            return _FakeCtxManager(SIMPLE_INDEX_BOTH_PRESENT)
        if "pypi.org/integrity/wave-sdk/2.2.0/" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, io.BytesIO(b"{}"))
        raise AssertionError(f"unexpected URL fetched: {url}")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        attested, missing = check_drift.pypi_attestations("2.2.0")

    assert attested is False
    assert sorted(missing) == [
        "wave_sdk-2.2.0-py3-none-any.whl",
        "wave_sdk-2.2.0.tar.gz",
    ]


def test_attestations_partial_when_only_some_files_have_provenance():
    def fake_urlopen(req, timeout=20):
        url = req.full_url
        if "pypi.org/simple/wave-sdk" in url:
            return _FakeCtxManager(SIMPLE_INDEX_BOTH_PRESENT)
        if url.endswith("wave_sdk-2.2.0-py3-none-any.whl/provenance"):
            return _FakeCtxManager(INTEGRITY_BUNDLE_PRESENT)
        if url.endswith("wave_sdk-2.2.0.tar.gz/provenance"):
            raise urllib.error.HTTPError(url, 404, "Not Found", None, io.BytesIO(b"{}"))
        raise AssertionError(f"unexpected URL fetched: {url}")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        attested, missing = check_drift.pypi_attestations("2.2.0")

    assert attested is True
    assert missing == ["wave_sdk-2.2.0.tar.gz"]


def test_simple_api_network_failure_is_unreadable_not_a_silent_pass():
    def fake_urlopen(req, timeout=20):
        raise urllib.error.HTTPError(req.full_url, 500, "Server Error", None, io.BytesIO(b"boom"))

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        pytest.raises(check_drift.UnreadableError),
    ):
        check_drift.pypi_attestations("2.2.0")


def test_integrity_api_non_404_error_is_unreadable_with_body_detail():
    """A real registry failure (e.g. a 500 or a genuine 403) must still raise
    UnreadableError -- distinct from the legitimate-404 "absent" case -- and
    must carry the response body so it is diagnosable."""

    def fake_urlopen(req, timeout=20):
        url = req.full_url
        if "pypi.org/simple/wave-sdk" in url:
            return _FakeCtxManager(SIMPLE_INDEX_BOTH_PRESENT)
        if "pypi.org/integrity/wave-sdk/2.2.0/" in url:
            raise urllib.error.HTTPError(url, 503, "Service Unavailable", None, io.BytesIO(b"try again later"))
        raise AssertionError(f"unexpected URL fetched: {url}")

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        pytest.raises(check_drift.UnreadableError, match="try again later"),
    ):
        check_drift.pypi_attestations("2.2.0")


def test_no_files_match_requested_version_is_unreadable():
    def fake_urlopen(req, timeout=20):
        return _FakeCtxManager(SIMPLE_INDEX_BOTH_PRESENT)

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        pytest.raises(check_drift.UnreadableError, match="no files matching version"),
    ):
        check_drift.pypi_attestations("9.9.9")


def test_files_for_version_does_not_match_a_prefix_of_another_version():
    """2.2.0 must not match a file that is actually 2.2.0rc1's wheel."""
    files = [
        {"filename": "wave_sdk-2.2.0rc1-py3-none-any.whl"},
        {"filename": "wave_sdk-2.2.0-py3-none-any.whl"},
    ]
    matched = check_drift._files_for_version(files, "2.2.0")
    assert [f["filename"] for f in matched] == ["wave_sdk-2.2.0-py3-none-any.whl"]
