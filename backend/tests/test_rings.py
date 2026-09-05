# tests/test_rings.py
# Tests for abuse ring detection, graph topology construction, and ring-aware scoring boost

import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app
from api.services.ring_service import get_ring_graph, list_rings
from api.services.decision_engine import DecisionEngine

client = TestClient(app)


def test_ring_graph_topology():
    """Verify that graph builder formats nodes and edges for radial cluster rendering."""
    graph = get_ring_graph(db=None, ring_id="ring_test_42")
    assert "nodes" in graph
    assert "edges" in graph
    assert "ring_id" in graph
    assert graph["ring_id"] == "ring_test_42"


def test_ring_boost_escalation():
    """Verify that ring affiliation elevates medium risk to Block."""
    engine = DecisionEngine(allow_threshold=0.40, challenge_threshold=0.75)

    # Base score in allow tier without ring boost
    tier_clean, score_clean, triggers_clean, _ = engine.evaluate(
        risk_score=0.35, ring_boost=0.0
    )
    assert tier_clean == "allow"
    assert len(triggers_clean) == 0

    # Same score with ring boost elevates to challenge
    tier_boosted, score_boosted, triggers_boosted, _ = engine.evaluate(
        risk_score=0.35, ring_boost=0.25, ring_id="ring_farm_01"
    )
    assert tier_boosted == "challenge"
    assert score_boosted == 0.60
    assert any("ring_farm_01" in t for t in triggers_boosted)

    # High base score + ring boost elevates directly to Block
    tier_blocked, score_blocked, triggers_blocked, reasoning = engine.evaluate(
        risk_score=0.60, ring_boost=0.25, ring_id="ring_farm_01"
    )
    assert tier_blocked == "block"
    assert score_blocked == 0.85
    assert "declined" in reasoning.lower()
