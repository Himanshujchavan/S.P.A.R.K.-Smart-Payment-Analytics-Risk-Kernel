-- 006_audit_event_type.sql
-- Discriminate auth/score/system events in audit_log without faking txn_id
-- for non-transaction events. Keeps txn_id as a real FK column (NULLable)
-- and adds actor_user_id + event_type for clean filtering.

ALTER TABLE audit_log
    ALTER COLUMN txn_id DROP NOT NULL;

ALTER TABLE audit_log
    ADD COLUMN IF NOT EXISTS event_type VARCHAR(20) NOT NULL DEFAULT 'score';

ALTER TABLE audit_log
    ADD COLUMN IF NOT EXISTS actor_user_id UUID REFERENCES users(user_id) ON DELETE SET NULL;

-- Backfill: existing rows default to event_type='score' which is correct for
-- pre-migration data (only scoring-related rows existed before Phase 1 auth
-- landed in this table layout).

CREATE INDEX IF NOT EXISTS idx_audit_log_event_type ON audit_log (event_type);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit_log (actor_user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log (created_at DESC);
