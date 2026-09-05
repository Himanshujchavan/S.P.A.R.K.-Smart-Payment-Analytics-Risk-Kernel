-- Integrity fixes and persisted decision thresholds
-- Remove duplicate score rows before enforcing one score per transaction.
DELETE FROM model_scores a
USING model_scores b
WHERE a.txn_id = b.txn_id
  AND (a.scored_at < b.scored_at OR (a.scored_at = b.scored_at AND a.score_id < b.score_id));

CREATE UNIQUE INDEX IF NOT EXISTS uq_model_scores_txn ON model_scores (txn_id);

CREATE TABLE IF NOT EXISTS decision_thresholds (
    config_id BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (config_id),
    allow_threshold NUMERIC(5,4) NOT NULL DEFAULT 0.45,
    challenge_threshold NUMERIC(5,4) NOT NULL DEFAULT 0.75,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_threshold_order CHECK (allow_threshold >= 0 AND challenge_threshold <= 1 AND allow_threshold < challenge_threshold)
);
INSERT INTO decision_thresholds (config_id) VALUES (TRUE) ON CONFLICT (config_id) DO NOTHING;
