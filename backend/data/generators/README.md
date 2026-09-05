# S.P.A.R.K. — Synthetic Data Generators

These three scripts produce the training dataset for the S.P.A.R.K. fraud
detection engine. They are *defense-only*: every value is synthetic and no
real cardholder data is referenced.

## Order of operations

Always run them in this order, after the database migrations are applied:

```bash
# 1. One-time infra setup (migrations, merchants, dashboard users)
psql -f db/migrations/001_init_schema.sql
psql -f db/migrations/002_hypertable_setup.sql
psql -f db/migrations/003_scoring_tables.sql
psql -f db/migrations/004_graph_tables.sql
psql -f db/migrations/005_auth_hardening.sql
psql -f db/migrations/006_audit_event_type.sql
psql -f db/seed/seed_data.sql

# 2. Generate the dataset
python -m data.generators.generate_transactions
python -m data.generators.generate_rings
python -m data.generators.generate_labels
python -m data.generators.verify_data
```

## What each script does

### `generate_transactions.py`

Seeds `buyers`, `devices`, and `buyer_device_link` rows, then writes a
configurable number of synthetic transactions across the active merchants.

Defaults: **2,000 buyers · 2,400 devices · 25,000 transactions · 60 days**.

```bash
python -m data.generators.generate_transactions \
    --buyers 2000 --devices 2400 --transactions 25000 --days 60
```

Key design choices:

- **Deterministic IDs.** Buyer / device / transaction UUIDs encode a
  monotonic index so re-running the script with the same args is idempotent
  and re-running with bigger args just appends.
- **Realistic Indian payment context.** Method mix is ~55% UPI, 30% card,
  10% netbanking, 4% wallet, 1% emandate. Amounts follow a long-tail
  distribution. Card BINs come from the 400000-499999 range. IPs are skewed
  toward plausible Indian ISP ranges.
- **City + lat/lng** are sampled from the top 8 Indian metros.
- **OS / browser mix** matches current mobile-first India: ~75% mobile.

### `generate_rings.py`

Injects **coordinated abuse-ring patterns** that a per-transaction scorer
will miss but the graph layer can catch.

```bash
python -m data.generators.generate_rings --rings 15
```

What it does per ring:

1. Picks 4-8 random buyers from the pool.
2. Allocates a shared attribute to that ring:
   - **device_fingerprint** (most common, ~65%) — creates a brand-new
     `devices` row and links every member to it.
   - **ip_address** (~20%) — stamps every member's recent transactions
     with a shared IP.
   - **card_bin** (~15%) — stamps every member's recent transactions
     with a shared card BIN.
3. Re-stamps a fraction of each member's recent transactions so the
   shared attribute appears at the *transaction* level (not just the
   link table).
4. Writes a `detected_rings` row with member count, density score, and
   flagged amount (sum of ring-member transaction volume).

### `generate_labels.py`

Generates ground-truth `is_fraud` labels for every transaction.

```bash
python -m data.generators.generate_labels
```

Fraud probability is a max-of-signals combiner (not a product — fraud is
driven by a few strong signals, not many weak ones):

| Signal                       | P(fraud) |
|------------------------------|----------|
| Ordinary txn                 | 1.2%     |
| Amount > ₹50,000             | 4%       |
| Hour between 1am-5am UTC     | 2.5%     |
| High velocity (burst buyer)  | 5-6%     |
| Ring member                  | 18%      |
| On a shared ring signal      | 28%      |

Label sources are assigned with `synthetic_seed` for clean traffic and
`chargeback_webhook` / `manual_review` for fraud — letting the model
eval pipeline reason about which ground-truth sources it trusts.

### `verify_data.py`

Sanity checks after generation:

- Row counts per table
- Every transaction has a label (no orphans)
- Ring count + max member count + max density
- Label source distribution
- Fraud rate sanity check (0.5% – 10%)

## Tuning for ML experiments

All scripts take a `--seed` flag. Use the same seed for comparable runs.

For a faster smoke-test pass (CI, pre-commit):

```bash
python -m data.generators.generate_transactions --buyers 100 --devices 120 --transactions 1000
python -m data.generators.generate_rings --rings 3
python -m data.generators.generate_labels
python -m data.generators.verify_data
```

For a full training pass (matches defaults in `train_model.py`):

```bash
python -m data.generators.generate_transactions
python -m data.generators.generate_rings
python -m data.generators.generate_labels
```

## Why this is in `data/generators/`, not in SQL

The seed SQL file (`db/seed/seed_data.sql`) exists for **demo** purposes —
a small fixed dataset with one example ring. The Python generators exist
for **ML** purposes — configurable, scalable, reproducible, and producing
realistic distributions the model can learn from.
