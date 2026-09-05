-- 002_hypertable_setup.sql
-- Converts transactions table to TimescaleDB hypertable & builds performance indexes

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Convert transactions table to hypertable partitioned by created_at (1 day chunks)
SELECT create_hypertable('transactions', 'created_at', if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 day');

-- Performance indexes for feature velocity, risk queries, and user lookups
CREATE INDEX IF NOT EXISTS idx_txn_buyer_time ON transactions (buyer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_txn_device_time ON transactions (device_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_txn_merchant_time ON transactions (merchant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_txn_card_bin ON transactions (card_bin, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_txn_ip ON transactions (ip_address, created_at DESC);
