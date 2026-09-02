import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app
from api.services.decision_engine import DecisionEngine
from api.schemas.score import ScoreRequest, RiskDecisionResponse


client = TestClient(app)


def test_decision_engine_tiers():
    """Verify three-tier decision engine rules and threshold boundaries."""
    engine = DecisionEngine(allow_threshold=0.40, challenge_threshold=0.75)

    # Allow tier
    tier, score, triggers, reasoning = engine.evaluate(risk_score=0.25)
    assert tier == "allow"
    assert score == 0.25
    assert "normally" in reasoning.lower()

    # Challenge tier
    tier, score, triggers, reasoning = engine.evaluate(risk_score=0.55)
    assert tier == "challenge"
    assert score == 0.55
    assert "challenge" in reasoning.lower()

    # Block tier
    tier, score, triggers, reasoning = engine.evaluate(risk_score=0.82)
    assert tier == "block"
    assert score == 0.82
    assert "declined" in reasoning.lower()

    # Ring boost elevates Allow to Challenge/Block
    tier_boosted, score_boosted, triggers, reasoning = engine.evaluate(
        risk_score=0.35, ring_boost=0.20, ring_id="ring_test_99"
    )
    assert score_boosted == 0.55
    assert tier_boosted == "challenge"
    assert any("ring_test_99" in t for t in triggers)


def test_score_endpoint_success():
    """Verify POST /api/v1/score returns valid RiskDecisionResponse with SHAP features."""
    payload = {
        "buyer_id": "usr_test_buyer_42",
        "amount": 2450.0,
        "method": "upi",
        "city": "Bengaluru",
        "ip_address": "10.0.0.1",
    }
    response = client.post("/api/v1/score", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "txn_id" in data
    assert "risk_score" in data
    assert "score" in data
    assert data["decision"] in ["allow", "challenge", "block"]
    assert data["tier"] == data["decision"]
    assert "model_version" in data
    assert isinstance(data["shap"], list)
    assert len(data["shap"]) > 0
    assert "top_features" in data
    assert isinstance(data["triggers"], list)


def test_score_endpoint_validation():
    """Verify input validation handles invalid amounts and missing buyer_id."""
    # Negative amount
    res = client.post(
        "/api/v1/score",
        json={"buyer_id": "usr_invalid", "amount": -100.0, "method": "upi"},
    )
    assert res.status_code == 422

    # Missing buyer_id
    res2 = client.post(
        "/api/v1/score",
        json={"amount": 500.0, "method": "upi"},
    )
    assert res2.status_code == 422


def test_rings_endpoint():
    """Verify GET /api/v1/rings returns ring clusters and graph structure."""
    res = client.get("/api/v1/rings")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    graph_res = client.get("/api/v1/rings/ring_mock_1/graph")
    assert graph_res.status_code == 200
    graph_data = graph_res.json()
    assert "nodes" in graph_data
    assert "edges" in graph_data


def test_model_health_endpoint():
    """Verify GET /api/v1/model/health returns model card and PSI drift series."""
    res = client.get("/api/v1/model/health")
    assert res.status_code == 200
    data = res.json()
    assert "model" in data
    assert "psi" in data
    assert "feature_drift" in data
    assert len(data["psi"]) > 0
    assert len(data["feature_drift"]) > 0
