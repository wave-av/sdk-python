"""WAVE SDK test configuration."""
import pytest


@pytest.fixture
def api_key():
    return "test-api-key"


@pytest.fixture
def wave_client():
    from wave import Wave
    return Wave(api_key="test-api-key", organization_id="org_test")
