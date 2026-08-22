# S.P.A.R.K.
### Smart Payment Analytics & Risk Kernel

**Track 02 — AI Risk Manager | Razorpay Buildathon**

A real-time fraud detection and risk decisioning engine built for Razorpay's test-mode transaction ecosystem. S.P.A.R.K. doesn't just flag fraud — it scores risk in three tiers, catches coordinated abuse rings that individual-transaction scoring misses, explains every decision with counterfactuals, and monitors its own model drift over time.

---

## 1. The Problem

Merchants lose revenue to fraud in two ways that most detectors get wrong:

1. **Binary block/allow systems are expensive on both sides.** Block too aggressively and you lose legitimate customers (false-positive cost). Block too leniently and fraud eats your margin (false-negative cost). Most systems only optimize for catching fraud and ignore the cost of wrongly blocking good customers.
2. **Per-transaction scoring misses coordinated fraud.** A ring of accounts sharing a device, IP, or card BIN can each make individually "normal-looking" transactions that add up to a large, structural fraud pattern — invisible to row-by-row scoring.

Fraud is also increasingly AI-assisted — automated card testing, synthetic identities, and adaptive evasion of static rule engines. A system that can't explain itself or notice when it's going stale falls behind quickly.

---

## 2. What S.P.A.R.K. Does

| Capability | Description |
|---|---|
| **Three-tier risk decisioning** | Every transaction is scored into Allow / Challenge / Block — not a binary cutoff. Medium-risk transactions get a lightweight step-up verification instead of an outright block, directly reducing false-positive cost. |
| **Abuse-ring detection** | A graph layer links accounts sharing devices, IPs, card BINs, or addresses, and flags densely connected clusters as probable coordinated fraud rings — catching what per-transaction scoring can't. |
| **Counterfactual explainability** | Every Challenge/Block decision comes with a plain-language counterfactual: what would have flipped the decision (e.g., "would have been Allowed if the amount was ₹2,000 lower"). |
| **Drift self-monitoring** | The system tracks its own live score distribution against training data (Population Stability Index) and flags itself when fraud patterns are shifting — before precision silently degrades. |
| **Full audit trail** | Every decision — model score, contributing features, ring membership, action taken — is logged immutably for compliance and review. |
| **Cost-based evaluation** | Reports precision/recall/F1 per tier, plus a ₹ cost curve comparing the three-tier system against a naive binary block/allow baseline, on a time-based held-out test set. |

**Strictly defense-only**: nothing in S.P.A.R.K. exposes exact thresholds, rules, or logic in a way that could help evade detection. Explanations are audit-facing, not customer-facing.

---

## 3. Tech Stack

| Layer | Technology |
|---|---|
| Transactional DB | PostgreSQL 16 + TimescaleDB (hypertables, time-partitioned) |
| Feature store / cache | Redis |
| Streaming ingestion | Apache Kafka (or Redpanda) |
| Graph storage | Apache AGE (Postgres extension) / NetworkX for local dev |
| Model | XGBoost / LightGBM |
| Model serving | FastAPI |
| Explainability | SHAP + custom counterfactual module |
| Experiment tracking | MLflow |
| Dashboard | Next.js + React + Tailwind + Recharts |
| Load simulation | Locust / custom async Python script |
| Containerization | Docker Compose (Kubernetes-ready) |

---

## 4. Folder Structure

```
spark/
├── README.md
├── docker-compose.yml
├── .env.example
│
├── backend/
│   │
│   ├── data/
│   │   ├── raw/                        # synthetic/seed transaction datasets
│   │   ├── processed/                  # feature-engineered training sets
│   │   └── generators/
│   │       ├── generate_transactions.py    # synthetic Razorpay-style txn generator
│   │       ├── generate_rings.py           # injects coordinated abuse-ring patterns
│   │       └── generate_labels.py          # synthetic fraud/chargeback labels
│   │
│   ├── db/
│   │   ├── migrations/
│   │   │   ├── 001_init_schema.sql         # merchants, users, devices, transactions
│   │   │   ├── 002_hypertable_setup.sql    # TimescaleDB hypertable config
│   │   │   ├── 003_scoring_tables.sql      # model_scores, audit_log, drift_snapshots
│   │   │   └── 004_graph_tables.sql        # detected_rings, edges
│   │   └── seed/
│   │       └── seed_data.sql
│   │
│   ├── ingestion/
│   │   ├── kafka_producer.py           # simulates incoming transaction stream
│   │   ├── kafka_consumer.py           # writes to Postgres, updates Redis features
│   │   └── feature_updater.py          # velocity/aggregate feature computation
│   │
│   ├── ml/
│   │   ├── features/
│   │   │   ├── feature_engineering.py  # behavioral, device, geo, card features
│   │   │   └── feature_schema.py
│   │   ├── training/
│   │   │   ├── train_model.py          # time-based split, XGBoost training
│   │   │   ├── threshold_calibration.py # cost-based Allow/Challenge/Block tuning
│   │   │   └── evaluate.py             # precision/recall/F1, cost curve generation
│   │   ├── explainability/
│   │   │   ├── shap_explainer.py
│   │   │   └── counterfactual.py
│   │   ├── drift/
│   │   │   └── psi_monitor.py          # population stability index tracking
│   │   └── models/                     # saved model artifacts (MLflow-tracked)
│   │
│   ├── graph/
│   │   ├── edge_builder.py             # builds shared-attribute edges from transactions
│   │   ├── ring_detector.py            # connected components / Louvain clustering
│   │   └── ring_scorer.py              # density + risk-based ring flagging
│   │
│   ├── api/
│   │   ├── main.py                     # FastAPI app entrypoint
│   │   ├── routers/
│   │   │   ├── score.py                 # POST /score — real-time scoring endpoint
│   │   │   ├── transactions.py          # transaction CRUD/query endpoints
│   │   │   ├── rings.py                 # ring lookup endpoints
│   │   │   └── audit.py                 # audit trail query endpoints
│   │   ├── services/
│   │   │   ├── scoring_service.py
│   │   │   ├── feature_assembly.py      # pulls Postgres + Redis features for inference
│   │   │   └── decision_engine.py       # applies calibrated thresholds
│   │   ├── schemas/                    # Pydantic request/response models
│   │   └── core/
│   │       ├── config.py                # env/config loading
│   │       └── db.py                    # DB session/connection setup
│   │
│   ├── simulation/
│   │   └── load_test.py                # Locust/async script for throughput demo
│   │
│   ├── notebooks/
│   │   ├── eda.ipynb                   # exploratory data analysis
│   │   └── model_evaluation.ipynb      # cost curve + metrics exploration
│   │
│   ├── tests/
│   │   ├── test_scoring.py
│   │   ├── test_features.py
│   │   └── test_ring_detector.py
│   │
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                           # Next.js dashboard
│   ├── app/
│   │   ├── page.tsx                     # live transaction feed
│   │   ├── metrics/
│   │   │   └── page.tsx                  # precision/recall/cost curve panel
│   │   ├── rings/
│   │   │   └── page.tsx                  # ring explorer (graph visualization)
│   │   ├── audit/
│   │   │   └── page.tsx                  # audit trail search/viewer
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── TransactionFeed.tsx
│   │   ├── MetricsPanel.tsx
│   │   ├── CostCurveChart.tsx
│   │   ├── RingGraph.tsx
│   │   └── AuditTrailViewer.tsx
│   ├── lib/
│   │   ├── api.ts                       # backend API client
│   │   └── types.ts                     # shared TS types
│   ├── public/
│   ├── package.json
│   ├── tailwind.config.ts
│   └── Dockerfile
│
└── docs/
    ├── architecture.md                 # full technical architecture doc
    └── demo_script.md                  # walkthrough script for judges
```

---

## 5. How It Works (End-to-End Flow)

1. A transaction hits the system via the Kafka producer (simulating Razorpay checkout traffic).
2. The consumer writes the raw transaction to TimescaleDB and updates Redis velocity features.
3. The FastAPI `/score` endpoint assembles features (Postgres + Redis), runs XGBoost inference, and returns a risk score.
4. The decision engine maps the score to Allow / Challenge / Block using cost-calibrated thresholds.
5. SHAP + counterfactual modules generate the explanation; everything is written to `model_scores` and `audit_log`.
6. In parallel, the graph layer checks if the user belongs to a growing abuse-ring cluster and boosts the risk score if so.
7. The dashboard surfaces live decisions, metrics, ring visualizations, and drift alerts.

---

## 6. Evaluation Methodology

- **Time-based train/test split** (not random) — trains on earlier transactions, tests on a later held-out window, mirroring real fraud drift.
- **Per-tier precision/recall/F1** reporting.
- **Cost curve**: ₹ cost of false positives vs. false negatives vs. challenge friction, compared against a naive binary system to quantify the savings from the three-tier design.
- **Honest exception list**: cases the model missed or over-flagged, documented rather than hidden.

---

## 7. Getting Started

```bash
# clone and set up environment
git clone <repo-url>
cd spark
cp .env.example .env

# start infra (Postgres+Timescale, Redis, Kafka)
docker-compose up -d

# --- backend setup ---
cd backend
pip install -r requirements.txt

# run DB migrations
psql -f db/migrations/001_init_schema.sql
psql -f db/migrations/002_hypertable_setup.sql
psql -f db/migrations/003_scoring_tables.sql
psql -f db/migrations/004_graph_tables.sql

# generate synthetic data
python data/generators/generate_transactions.py
python data/generators/generate_rings.py
python data/generators/generate_labels.py

# train model
python ml/training/train_model.py

# start API
uvicorn api.main:app --reload
# API now running at http://localhost:8000

# --- frontend setup (new terminal) ---
cd frontend
npm install
npm run dev
# dashboard now running at http://localhost:3000

# --- load simulation (optional, new terminal) ---
cd backend
python simulation/load_test.py --rate 1000
```

---

## 8. Team / Track

**Track 02 — AI Risk Manager**
Objective: build a detector, verifier, or auto-responder for one class of loss (fraud), with measured precision/recall and false-positive cost on a held-out test set, strictly defense-only.