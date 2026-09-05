# api/services/decision_engine.py
# Three-tier decision engine mapping risk scores and triggers to Allow, Challenge, or Block.

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Default calibrated thresholds (score in range 0.0 to 1.0)
DEFAULT_ALLOW_THRESHOLD: float = 0.45
DEFAULT_CHALLENGE_THRESHOLD: float = 0.75


class DecisionEngine:
    """Evaluates raw model scores against calibrated business cost thresholds

    and rule triggers (e.g. ring membership, high velocity bursts).
    """

    def __init__(
        self,
        allow_threshold: float = DEFAULT_ALLOW_THRESHOLD,
        challenge_threshold: float = DEFAULT_CHALLENGE_THRESHOLD,
    ):
        self.allow_threshold = allow_threshold
        self.challenge_threshold = challenge_threshold

    def update_thresholds(self, allow: float, challenge: float) -> None:
        """Dynamically update thresholds (e.g., from calibration run or DB)."""
        if allow >= challenge:
            raise ValueError(f"Allow threshold ({allow}) must be strictly less than challenge ({challenge}).")
        self.allow_threshold = allow
        self.challenge_threshold = challenge
        logger.info(f"DecisionEngine thresholds updated: allow={allow:.3f}, challenge={challenge:.3f}")

    def evaluate(
        self,
        risk_score: float,
        ring_boost: float = 0.0,
        ring_id: Optional[str] = None,
        velocity_flags: Optional[List[str]] = None,
    ) -> Tuple[str, float, List[str], str]:
        """Compute the final three-tier decision, effective score, triggers, and reasoning.

        Args:
            risk_score: Model raw probability score (0.0 to 1.0)
            ring_boost: Risk score increment if buyer is linked to an active ring
            ring_id: Identifier of matched ring
            velocity_flags: Any heuristic velocity warnings triggered

        Returns:
            (tier, final_score, triggers, reasoning)
        """
        triggers: List[str] = []
        final_score = min(1.0, max(0.0, risk_score + ring_boost))

        if ring_boost > 0 and ring_id:
            triggers.append(f"Ring membership ({ring_id}) +{ring_boost:.2f}")

        if velocity_flags:
            triggers.extend(velocity_flags)

        # Three-tier threshold classification
        if final_score >= self.challenge_threshold:
            tier = "block"
            if ring_boost > 0:
                reasoning = (
                    f"Risk score {final_score:.2f} exceeded Block threshold ({self.challenge_threshold:.2f}); "
                    f"boosted by active abuse ring affiliation ({ring_id}). Transaction declined."
                )
            else:
                reasoning = (
                    f"Risk score {final_score:.2f} exceeded Block threshold ({self.challenge_threshold:.2f}). "
                    f"High probability of fraud across key behavioral and device signals. Transaction declined."
                )

        elif final_score >= self.allow_threshold:
            tier = "challenge"
            reasoning = (
                f"Risk score {final_score:.2f} within Challenge band "
                f"[{self.allow_threshold:.2f} - {self.challenge_threshold:.2f}]. Step-up 2FA/OTP recommended."
            )
            triggers.append("Medium risk step-up verification required")
        else:
            tier = "allow"
            reasoning = (
                f"Risk score {final_score:.2f} well below Challenge threshold ({self.allow_threshold:.2f}). "
                "Transaction proceeds normally."
            )

        return tier, final_score, triggers, reasoning


# Global shared instance
decision_engine = DecisionEngine()
