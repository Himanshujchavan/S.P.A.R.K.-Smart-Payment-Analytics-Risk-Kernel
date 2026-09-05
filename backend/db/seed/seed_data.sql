-- DEV/DEMO SEED DATA ONLY — do not run against a real merchant environment
-- Seed script for S.P.A.R.K. database testing

-- 1. Merchants (3 merchants)
INSERT INTO merchants (merchant_id, name, razorpay_key_id, status) VALUES
  ('11111111-1111-4111-8111-111111111111', 'Acme E-Commerce', 'rzp_test_AcmeKey123', 'active'),
  ('22222222-2222-4222-8222-222222222222', 'Nexus Digital Goods', 'rzp_test_NexusKey456', 'active'),
  ('33333333-3333-4333-8333-333333333333', 'Zenith Travel', 'rzp_test_ZenithKey789', 'active')
ON CONFLICT (merchant_id) DO NOTHING;

-- 2. Test Dashboard Users (hashed bcrypt password: 'password123')
-- Hash generated via bcrypt: $2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeg6Lruj3vjPGga31lW
INSERT INTO users (user_id, merchant_id, email, phone, password_hash, full_name, role) VALUES
  ('a1111111-1111-4111-8111-111111111111', '11111111-1111-4111-8111-111111111111', 'admin@spark.local', '+919876543210', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeg6Lruj3vjPGga31lW', 'Admin User', 'Merchant Owner'),
  ('a2222222-2222-4222-8222-222222222222', '11111111-1111-4111-8111-111111111111', 'analyst@merchant.com', '+919876543211', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeg6Lruj3vjPGga31lW', 'Harsh Risk Analyst', 'Risk Analyst')
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO auth_providers (user_id, provider_name, provider_user_id) VALUES
  ('a1111111-1111-4111-8111-111111111111', 'email', 'admin@spark.local'),
  ('a2222222-2222-4222-8222-222222222222', 'email', 'analyst@merchant.com')
ON CONFLICT DO NOTHING;

-- 3. Seed Buyers (60 buyers) & Devices (75 devices)
DO $$
DECLARE
    b_id UUID;
    d_id UUID;
    shared_dev_id UUID := 'd9999999-9999-4999-8999-999999999999';
    m_id UUID;
    t_id UUID;
    i INT;
    j INT;
    is_fraud_val BOOLEAN;
    score_val NUMERIC;
    decision_val VARCHAR(20);
    dt TIMESTAMPTZ;
BEGIN
    -- Shared Device for ring detection testing (5 buyers share this 1 device)
    INSERT INTO devices (device_id, fingerprint, os, browser)
    VALUES (shared_dev_id, 'dev_shared_cluster_001', 'Android', 'Chrome Mobile')
    ON CONFLICT (device_id) DO NOTHING;

    -- Create 60 buyers and devices
    FOR i IN 1..60 LOOP
        b_id := CAST('b0000000-0000-4000-8000-' || LPAD(i::text, 12, '0') AS UUID);
        d_id := CAST('d0000000-0000-4000-8000-' || LPAD(i::text, 12, '0') AS UUID);

        INSERT INTO buyers (buyer_id, name, email, phone)
        VALUES (b_id, 'Buyer ' || i, 'buyer' || i || '@example.com', '+9199000' || LPAD(i::text, 5, '0'))
        ON CONFLICT (buyer_id) DO NOTHING;

        INSERT INTO devices (device_id, fingerprint, os, browser)
        VALUES (d_id, 'fp_dev_' || LPAD(i::text, 6, '0'), CASE WHEN i % 2 = 0 THEN 'iOS' ELSE 'Android' END, 'Safari')
        ON CONFLICT (device_id) DO NOTHING;

        -- Link buyer to their main device
        INSERT INTO buyer_device_link (buyer_id, device_id) VALUES (b_id, d_id) ON CONFLICT DO NOTHING;

        -- Injected shared device cluster: buyers 1 to 5 ALL share the shared_dev_id device
        IF i <= 5 THEN
            INSERT INTO buyer_device_link (buyer_id, device_id) VALUES (b_id, shared_dev_id) ON CONFLICT DO NOTHING;
        END IF;
    END LOOP;

    -- Extra devices (up to 75 total)
    FOR i IN 61..75 LOOP
        d_id := CAST('d0000000-0000-4000-8000-' || LPAD(i::text, 12, '0') AS UUID);
        INSERT INTO devices (device_id, fingerprint, os, browser)
        VALUES (d_id, 'fp_extra_dev_' || LPAD(i::text, 6, '0'), 'Windows', 'Chrome')
        ON CONFLICT (device_id) DO NOTHING;
    END LOOP;

    -- 4. Seed 500+ Transactions across the last 30 days
    FOR i IN 1..520 LOOP
        t_id := CAST('e0000000-0000-4000-8000-' || LPAD(i::text, 12, '0') AS UUID);
        b_id := CAST('b0000000-0000-4000-8000-' || LPAD(((i % 60) + 1)::text, 12, '0') AS UUID);
        
        -- Use shared device for cluster buyers occasionally
        IF i % 10 = 0 THEN
            d_id := shared_dev_id;
        ELSE
            d_id := CAST('d0000000-0000-4000-8000-' || LPAD(((i % 75) + 1)::text, 12, '0') AS UUID);
        END IF;

        IF i % 3 = 0 THEN
            m_id := '11111111-1111-4111-8111-111111111111';
        ELSIF i % 3 = 1 THEN
            m_id := '22222222-2222-4222-8222-222222222222';
        ELSE
            m_id := '33333333-3333-4333-8333-333333333333';
        END IF;

        -- Spread created_at across 30 days
        dt := NOW() - ((520 - i) * INTERVAL '80 minutes');

        -- Fraud logic simulation for ground truth labels
        is_fraud_val := (i % 17 = 0 OR (i % 10 = 0 AND i > 400));
        
        IF is_fraud_val THEN
            score_val := 82.5;
            decision_val := 'block';
        ELSIF i % 7 = 0 THEN
            score_val := 54.0;
            decision_val := 'challenge';
        ELSE
            score_val := 12.0;
            decision_val := 'allow';
        END IF;

        INSERT INTO transactions (txn_id, created_at, merchant_id, buyer_id, device_id, amount, currency, method, card_bin, ip_address, city)
        VALUES (
            t_id,
            dt,
            m_id,
            b_id,
            d_id,
            ROUND((150 + (i * 37) % 9500)::numeric, 2),
            'INR',
            CASE WHEN i % 4 = 0 THEN 'upi' WHEN i % 4 = 1 THEN 'card' WHEN i % 4 = 2 THEN 'netbanking' ELSE 'wallet' END,
            LPAD(((400000 + (i * 13) % 9999))::text, 6, '0'),
            '10.0.' || (i % 250) || '.' || ((i * 3) % 250),
            CASE WHEN i % 4 = 0 THEN 'Bengaluru' WHEN i % 4 = 1 THEN 'Mumbai' WHEN i % 4 = 2 THEN 'Delhi' ELSE 'Pune' END
        ) ON CONFLICT DO NOTHING;

        -- Matching fraud label for EVERY transaction (no orphans)
        INSERT INTO fraud_labels (txn_id, is_fraud, label_source, updated_at)
        VALUES (t_id, is_fraud_val, 'synthetic_seed', dt)
        ON CONFLICT DO NOTHING;

        -- Matching model score
        INSERT INTO model_scores (txn_id, risk_score, decision, model_version, scored_at)
        VALUES (t_id, score_val, decision_val, 'xgboost-v2.4.1', dt)
        ON CONFLICT DO NOTHING;

    END LOOP;

    -- Sample Audit Entries
    FOR i IN 1..40 LOOP
        t_id := CAST('e0000000-0000-4000-8000-' || LPAD((i * 12)::text, 12, '0') AS UUID);
        dt := NOW() - (i * INTERVAL '6 hours');
        INSERT INTO audit_log (txn_id, action, triggered_by, reasoning, created_at)
        VALUES (
            t_id,
            CASE WHEN i % 3 = 0 THEN 'block' WHEN i % 3 = 1 THEN 'challenge' ELSE 'allow' END,
            CASE WHEN i % 3 = 0 THEN 'Ring membership' WHEN i % 3 = 1 THEN 'Score in challenge band' ELSE 'Model score' END,
            'Automated risk assessment evaluated decision.',
            dt
        ) ON CONFLICT DO NOTHING;
    END LOOP;

    -- Sample Detected Ring
    INSERT INTO detected_rings (ring_id, member_count, density_score, shared_attribute, shared_value, status, flagged_amount, account_ids, detected_at)
    VALUES (
        'r1111111-1111-4111-8111-111111111111',
        5,
        0.830,
        'device_fingerprint',
        'dev_shared_cluster_001',
        'active',
        184320.00,
        '["b0000000-0000-4000-8000-000000000001", "b0000000-0000-4000-8000-000000000002", "b0000000-0000-4000-8000-000000000003", "b0000000-0000-4000-8000-000000000004", "b0000000-0000-4000-8000-000000000005"]'::jsonb,
        NOW() - INTERVAL '2 hours'
    ) ON CONFLICT DO NOTHING;

END $$;
