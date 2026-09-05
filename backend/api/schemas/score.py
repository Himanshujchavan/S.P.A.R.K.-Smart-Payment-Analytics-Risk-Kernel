# api/schemas/score.py
# Pydantic schemas for real-time risk scoring and decisions

from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ScoreRequest(BaseModel):
    """Transaction payload sent for real-time scoring."""
    txn_id: Optional[str] = Field(None, description="Unique transaction ID (generated if omitted)")
    merchant_id: Optional[str] = Field(None, description="Razorpay merchant ID")
    buyer_id: str = Field(..., description="Unique buyer / customer identifier")
    device_id: Optional[str] = Field(None, description="Device fingerprint or ID")
    amount: float = Field(..., gt=0, description="Transaction amount in INR")
    currency: str = Field("INR", description="Three-letter currency code")
    method: str = Field("upi", description="Payment method: upi, card, netbanking, wallet, emandate")
    card_bin: Optional[str] = Field(None, description="First 6 digits of card BIN if payment is card")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    city: Optional[str] = Field(None, description="Transaction city")
    created_at: Optional[str] = Field(None, description="ISO 8601 transaction timestamp")


class FeatureContribution(BaseModel):
    feature: str
    value: Any
    shap_value: float
    description: Optional[str] = None


class CounterfactualDetail(BaseModel):
    feature: Optional[str] = None
    original_value: Optional[Any] = None
    suggested_value: Optional[Any] = None
    new_score: Optional[float] = None
    text: Optional[str] = None


class RiskDecisionResponse(BaseModel):
    """Three-tier risk decision response returned by POST /api/v1/score."""
    txn_id: str
    risk_score: float = Field(..., description="Calibrated risk score between 0.0 and 1.0 (or 0-100 scale)")
    score: float = Field(..., description="0-100 normalized score for dashboard display")
    decision: str = Field(..., description="Three-tier decision: allow, challenge, block")
    tier: str = Field(..., description="Alias for decision ('allow', 'challenge', 'block')")
    model_version: str = Field(..., description="Deployed model artifact version")
    ring_id: Optional[str] = Field(None, description="ID of flagged ring if buyer is a member")
    ring_risk_boost: float = Field(0.0, description="Risk increment applied from ring affiliation")
    counterfactual: Optional[str] = Field(None, description="Plain-language counterfactual advice")
    counterfactual_details: Optional[List[CounterfactualDetail]] = None
    shap: List[Dict[str, Any]] = Field(default_factory=list, description="SHAP feature importance list")
    top_features: List[str] = Field(default_factory=list, description="Top risk contributing feature names")
    triggers: List[str] = Field(default_factory=list, description="Reason triggers (e.g. Model score, Ring membership)")

    model_config = {"protected_namespaces": ()}

