"""MeshAPI: every method, reads and mutations alike, builds the x-wave-node header before it sends
anything, and the mutations are sent once."""
from __future__ import annotations

import httpx
import pytest

from tests.conftest import live_response
from wave_sdk.errors import WaveError


def sent(recorder) -> tuple[str, str]:
    req = recorder.last
    return req.method, req.url.raw_path.decode()


def test_mesh_requires_a_node_before_sending(wave, recorder):
    with pytest.raises(ValueError, match="x-wave-node"):
        wave.mesh.list_peers()
    assert recorder.requests == []


def test_mesh_sends_the_node_header(wave, recorder):
    recorder.set(lambda _r: live_response("mesh_peers"))
    wave.mesh.node = "studio-a"
    peers = wave.mesh.list_peers()
    assert sent(recorder) == ("GET", "/v1/mesh/peers")
    assert recorder.last.headers["x-wave-node"] == "studio-a"
    assert peers == {"count": 0, "org": "org_fixture", "peers": []}
    wave.mesh.list_peers(node="studio-b")
    assert recorder.last.headers["x-wave-node"] == "studio-b"


# Every MeshAPI method, mutations included, with the (verb, path) it sends.
MESH_CALLS = [
    ("list_peers", (), ("GET", "/v1/mesh/peers")),
    ("list_regions", (), ("GET", "/v1/mesh/regions")),
    ("get_region", ("r1",), ("GET", "/v1/mesh/regions/r1")),
    ("get_region_health", ("r1",), ("GET", "/v1/mesh/regions/r1/health")),
    ("add_peer", ("r1", "https://peer.example"), ("POST", "/v1/mesh/regions/r1/peers")),
    ("remove_peer", ("p1",), ("DELETE", "/v1/mesh/peers/p1")),
    ("create_policy", ("p", "priority", "r1", ["r2"]), ("POST", "/v1/mesh/policies")),
    ("list_policies", (), ("GET", "/v1/mesh/policies")),
    ("trigger_failover", ("pol1", "r2"), ("POST", "/v1/mesh/policies/pol1/failover")),
    ("get_replication_status", (), ("GET", "/v1/mesh/replication")),
    ("get_topology", (), ("GET", "/v1/mesh/topology")),
]
MESH_MUTATIONS = {"add_peer", "remove_peer", "create_policy", "trigger_failover"}


def test_mesh_calls_cover_every_public_method(wave):
    public = {m for m in dir(wave.mesh) if not m.startswith("_") and callable(getattr(wave.mesh, m))}
    assert public == {name for name, _args, _route in MESH_CALLS}


@pytest.mark.parametrize("method, args, route", MESH_CALLS, ids=[c[0] for c in MESH_CALLS])
def test_every_mesh_method_refuses_to_send_without_a_node(wave, recorder, method, args, route):
    with pytest.raises(ValueError, match="x-wave-node"):
        getattr(wave.mesh, method)(*args)
    assert recorder.requests == []


@pytest.mark.parametrize("method, args, route", MESH_CALLS, ids=[c[0] for c in MESH_CALLS])
def test_every_mesh_method_sends_the_node_header(wave, recorder, method, args, route):
    """Reads and mutations alike carry x-wave-node: the client default, or a per-call override."""
    ok = {
        "create_policy": {"id": "pol1", "organization_id": "o", "name": "p", "strategy": "priority", "primary_region": "r1", "fallback_regions": ["r2"], "created_at": "t", "updated_at": "t"},
        "get_region": {"id": "r1", "name": "n", "provider": "p", "location": "l", "status": "up", "latency_ms": 1, "capacity_percent": 1.0, "stream_count": 0, "viewer_count": 0, "is_primary": True, "created_at": "t", "updated_at": "t"},
        "get_replication_status": [],
    }.get(method, {})
    recorder.set(lambda _r: httpx.Response(200, json=ok))
    wave.mesh.node = "studio-a"
    getattr(wave.mesh, method)(*args)
    assert sent(recorder) == route
    assert recorder.last.headers["x-wave-node"] == "studio-a"
    getattr(wave.mesh, method)(*args, node="studio-b")
    assert recorder.last.headers["x-wave-node"] == "studio-b"


@pytest.mark.parametrize("method", sorted(MESH_MUTATIONS))
def test_mesh_mutations_are_sent_once(wave, recorder, monkeypatch, method):
    """A 503 after the server applied the change must not add a second peer or fail over twice."""
    monkeypatch.setattr("wave_sdk.client.time.sleep", lambda _s: None)
    recorder.set(lambda _r: httpx.Response(503, json={"error": {"code": "UPSTREAM_ERROR", "message": "m"}}))
    args = next(a for name, a, _route in MESH_CALLS if name == method)
    with pytest.raises(WaveError):
        getattr(wave.mesh, method)(*args, node="studio-a")
    assert len(recorder.requests) == 1


def test_mesh_reads_are_still_retried(wave, recorder, monkeypatch):
    monkeypatch.setattr("wave_sdk.client.time.sleep", lambda _s: None)
    replies = iter([httpx.Response(503, json={"error": {"code": "UPSTREAM_ERROR", "message": "m"}}), live_response("mesh_peers")])
    recorder.set(lambda _r: next(replies))
    assert wave.mesh.list_peers(node="studio-a")["peers"] == []
    assert len(recorder.requests) == 2


@pytest.mark.parametrize("method, args, route", MESH_CALLS, ids=[c[0] for c in MESH_CALLS])
@pytest.mark.parametrize("override", ["", "   "], ids=["empty", "blank"])
def test_an_empty_override_never_falls_back_to_the_default_node(wave, recorder, method, args, route, override):
    """``node=""`` with a client default set must raise, not quietly target the default node: a
    multi-node caller whose config value came back empty would otherwise read from, or mutate,
    the wrong node."""
    recorder.set(lambda _r: httpx.Response(200, json={}))
    wave.mesh.node = "studio-a"
    with pytest.raises(ValueError, match="x-wave-node"):
        getattr(wave.mesh, method)(*args, node=override)
    assert recorder.requests == []


def test_node_none_means_use_the_default(wave, recorder):
    recorder.set(lambda _r: live_response("mesh_peers"))
    wave.mesh.node = "studio-a"
    wave.mesh.list_peers(node=None)
    assert recorder.last.headers["x-wave-node"] == "studio-a"


def test_a_blank_default_node_is_rejected(wave, recorder):
    wave.mesh.node = "  "
    with pytest.raises(ValueError, match="x-wave-node"):
        wave.mesh.list_peers()
    assert recorder.requests == []


@pytest.mark.parametrize("node", ["studio-a\r\nx-evil: 1", "studio\n"])
def test_mesh_rejects_a_multi_line_node_name(wave, recorder, node):
    with pytest.raises(ValueError, match="single-line"):
        wave.mesh.list_peers(node=node)
    assert recorder.requests == []


def test_mesh_ids_stay_one_path_segment(wave, recorder):
    recorder.set(lambda _r: httpx.Response(200, json={}))
    wave.mesh.remove_peer("a/b?c", node="studio-a")
    assert sent(recorder) == ("DELETE", "/v1/mesh/peers/a%2Fb%3Fc")
    with pytest.raises(ValueError):
        wave.mesh.trigger_failover("..", "r2", node="studio-a")
