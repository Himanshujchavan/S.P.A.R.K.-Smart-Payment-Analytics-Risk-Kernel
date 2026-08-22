-- 001_init_schema.sql
-- Base table definitions for S.P.A.R.K. database

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Merchants (business accounts)
CREATE TABLE IF NOT EXISTS merchants (
    merchant_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    razorpay_key_id VARCHAR(100) UNIQUE,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Users (dashboard logins — merchants/analysts)
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    merchant_id UUID REFERENCES merchants(merchant_id) ON DELETE SET NULL,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(50) UNIQUE,
    password_hash VARCHAR(255),
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'Risk Analyst',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_email_or_phone CHECK (email IS NOT NULL OR phone IS NOT NULL)
);

-- 3. Auth Providers (OAuth / SSO connections)
CREATE TABLE IF NOT EXISTS auth_providers (
    provider_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    provider_name VARCHAR(50) NOT NULL,
    provider_user_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_provider UNIQUE (user_id, provider_name)
);

-- 4. Sessions (JWT Refresh tokens)
CREATE TABLE IF NOT EXISTS sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    refresh_token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Buyers (end-customers whose transactions are scored)
CREATE TABLE IF NOT EXISTS buyers (
    buyer_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. Devices (device fingerprints)
CREATE TABLE IF NOT EXISTS devices (
    device_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fingerprint VARCHAR(255) UNIQUE NOT NULL,
    os VARCHAR(50),
    browser VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. Buyer Device Link (many-to-many relationship)
CREATE TABLE IF NOT EXISTS buyer_device_link (
    buyer_id UUID NOT NULL REFERENCES buyers(buyer_id) ON DELETE CASCADE,
    device_id UUID NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (buyer_id, device_id)
);

-- 8. Transactions (Base table before TimescaleDB hypertable conversion)
CREATE TABLE IF NOT EXISTS transactions (
    txn_id UUID NOT NULL DEFAULT uuid_generate_v4(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    merchant_id UUID NOT NULL REFERENCES merchants(merchant_id) ON DELETE CASCADE,
    buyer_id UUID NOT NULL REFERENCES buyers(buyer_id) ON DELETE CASCADE,
    device_id UUID REFERENCES devices(device_id) ON DELETE SET NULL,
    amount NUMERIC(12, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    method VARCHAR(20) NOT NULL,
    card_bin VARCHAR(6),
    ip_address VARCHAR(45),
    city VARCHAR(100),
    PRIMARY KEY (txn_id, created_at)
);
