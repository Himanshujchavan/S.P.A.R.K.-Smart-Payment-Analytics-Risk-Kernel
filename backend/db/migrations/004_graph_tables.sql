-- 004_graph_tables.sql
-- Graph layer storage for detected abuse rings

CREATE TABLE IF NOT EXISTS detected_rings (
    ring_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    member_count INT NOT NULL,
    density_score NUMERIC(4, 3) NOT NULL,
    shared_attribute VARCHAR(50) NOT NULL,
    shared_value VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    flagged_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    account_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rings_status ON detected_rings (status);
