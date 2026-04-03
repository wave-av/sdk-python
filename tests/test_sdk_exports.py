"""
SDK Export Verification Tests

Validates that all 33 SDK modules import correctly, all API classes
instantiate with WaveClient, and the Wave convenience class wires everything.
"""

import pytest


def test_all_modules_import():
    """All 33 API modules should be importable from wave package."""
    from wave import (
        ClipsAPI, EditorAPI, VoiceAPI, PhoneAPI, CollabAPI,
        CaptionsAPI, ChaptersAPI, StudioAIAPI, TranscribeAPI,
        SentimentAPI, SearchAPI, SceneAPI,
        PipelineAPI, StudioAPI,
        FleetAPI, GhostAPI, MeshAPI, EdgeAPI, PulseAPI, PrismAPI, ZoomAPI,
        VaultAPI, MarketplaceAPI, ConnectAPI, DistributionAPI,
        DesktopAPI, SignageAPI, QrAPI, AudienceAPI, CreatorAPI,
        PodcastAPI, SlidesAPI, UsbAPI,
    )
    # All should be classes
    assert callable(ClipsAPI)
    assert callable(PipelineAPI)
    assert callable(PrismAPI)
    assert callable(UsbAPI)


def test_wave_client_import():
    """Core client classes should import."""
    from wave import WaveClient, WaveError, RateLimitError
    assert callable(WaveClient)
    assert issubclass(WaveError, Exception)
    assert issubclass(RateLimitError, WaveError)


def test_wave_client_requires_api_key():
    """WaveClient should raise ValueError without api_key."""
    from wave import WaveClient
    with pytest.raises(ValueError, match="api_key"):
        WaveClient(api_key="")


def test_wave_convenience_class():
    """Wave class should instantiate with all 33 API modules."""
    from wave import Wave
    w = Wave(api_key="test-key")

    # Existing P3
    assert hasattr(w, 'clips')
    assert hasattr(w, 'editor')
    assert hasattr(w, 'voice')
    assert hasattr(w, 'phone')
    assert hasattr(w, 'collab')
    assert hasattr(w, 'captions')
    assert hasattr(w, 'chapters')
    assert hasattr(w, 'studio_ai')
    assert hasattr(w, 'transcribe')
    assert hasattr(w, 'sentiment')
    assert hasattr(w, 'search')
    assert hasattr(w, 'scene')

    # P1
    assert hasattr(w, 'pipeline')
    assert hasattr(w, 'studio')

    # P2
    assert hasattr(w, 'fleet')
    assert hasattr(w, 'ghost')
    assert hasattr(w, 'mesh')
    assert hasattr(w, 'edge')
    assert hasattr(w, 'pulse')
    assert hasattr(w, 'prism')
    assert hasattr(w, 'zoom')

    # P3 new
    assert hasattr(w, 'vault')
    assert hasattr(w, 'marketplace')
    assert hasattr(w, 'connect')
    assert hasattr(w, 'distribution')
    assert hasattr(w, 'desktop')
    assert hasattr(w, 'signage')
    assert hasattr(w, 'qr')
    assert hasattr(w, 'audience')
    assert hasattr(w, 'creator')

    # P4
    assert hasattr(w, 'podcast')
    assert hasattr(w, 'slides')
    assert hasattr(w, 'usb')


def test_api_count():
    """Wave class should have exactly 33 API bindings (+ client)."""
    from wave import Wave
    w = Wave(api_key="test-key")
    api_attrs = [a for a in dir(w) if not a.startswith('_') and a != 'client']
    assert len(api_attrs) == 33, f"Expected 33 APIs, got {len(api_attrs)}: {api_attrs}"


def test_pipeline_has_methods():
    """PipelineAPI should have expected methods."""
    from wave import Wave
    w = Wave(api_key="test-key")
    for method in ['create', 'get', 'list', 'start', 'stop', 'get_health', 'wait_for_live']:
        assert hasattr(w.pipeline, method), f"PipelineAPI missing {method}"


def test_prism_has_methods():
    """PrismAPI should have expected methods."""
    from wave import Wave
    w = Wave(api_key="test-key")
    for method in ['create_device', 'start_device', 'stop_device', 'discover_sources', 'get_presets', 'set_preset', 'recall_preset']:
        assert hasattr(w.prism, method), f"PrismAPI missing {method}"


def test_studio_has_methods():
    """StudioAPI should have expected methods."""
    from wave import Wave
    w = Wave(api_key="test-key")
    for method in ['create', 'start', 'stop', 'add_source', 'activate_scene', 'transition', 'set_program', 'get_audio_mix']:
        assert hasattr(w.studio, method), f"StudioAPI missing {method}"


def test_version():
    """SDK version should be 2.0.0."""
    import wave
    assert wave.__version__ == "2.0.0"


def test_all_exports():
    """__all__ should contain all API classes."""
    import wave
    expected = [
        "ClipsAPI", "EditorAPI", "VoiceAPI", "PhoneAPI", "CollabAPI",
        "CaptionsAPI", "ChaptersAPI", "StudioAIAPI", "TranscribeAPI",
        "SentimentAPI", "SearchAPI", "SceneAPI",
        "PipelineAPI", "StudioAPI",
        "FleetAPI", "GhostAPI", "MeshAPI", "EdgeAPI", "PulseAPI",
        "PrismAPI", "ZoomAPI",
        "VaultAPI", "MarketplaceAPI", "ConnectAPI", "DistributionAPI",
        "DesktopAPI", "SignageAPI", "QrAPI", "AudienceAPI", "CreatorAPI",
        "PodcastAPI", "SlidesAPI", "UsbAPI",
    ]
    for cls in expected:
        assert cls in wave.__all__, f"{cls} missing from __all__"
