-- 003_scoring_tables.sql
-- Scoring, audit, and model monitoring tables

-- 1. Fraud Labels (Ground truth chargeback/fraud outcomes)
CREATE TABLE IF NOT EXISTS fraud_labels (
    label_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    txn_id UUID NOT NULL,
    is_fraud BOOLEAN NOT NULL DEFAULT FALSE,
    label_source VARCHAR(50) NOT NULL DEFAULT 'synthetic_seed',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fraud_labels_txn ON fraud_labels (txn_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_fraud_labels_txn ON fraud_labels (txn_id);

-- 2. Model Scores (XGBoost inference scores, decision tier & SHAP explainability)
CREATE TABLE IF NOT EXISTS model_scores (
    score_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    txn_id UUID NOT NULL,
    risk_score NUMERIC(5, 2) NOT NULL,
    decision VARCHAR(20) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    ring_id UUID,
    counterfactual TEXT,
    top_features JSONB,
    scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_model_scores_txn ON model_scores (txn_id);

-- 3. Audit Log (Immutable decision audit trail for compliance)
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    txn_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,
    triggered_by VARCHAR(100) NOT NULL,
    reasoning TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_txn ON audit_log (txn_id);

-- 4. Drift Snapshots (Population Stability Index over time)
CREATE TABLE IF NOT EXISTS drift_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    snapshot_date DATE NOT NULL UNIQUE,
    psi_score NUMERIC(6, 4) NOT NULL,
    feature_drift JSONB,
    alert_triggered BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
