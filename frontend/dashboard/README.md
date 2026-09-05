# S.P.A.R.K. Dashboard (`spark-dashboard`)

A state-of-the-art Next.js 16 + React 19 web application built for **Razorpay Buildathon — Track 02 (AI Risk Manager)**. The dashboard provides real-time fraud monitoring, 3-tier risk decisioning, abuse-ring graph exploration, counterfactual explainability, model drift tracking, and interactive traffic load simulation.

---

## 🚀 Quick Start

Run inside `frontend/dashboard`:

```bash
# Install dependencies
npm install

# Run development server
npm run dev
# Dashboard runs at http://localhost:3000

# Build for production
npm run build
```

---

## 📄 Page Content & Copy Specification

For the complete UI microcopy, form field labels, empty states, error states, and UX voice guidelines, see [`docs/page_copy_spec.md`](file:///C:/Users/chava/S.P.A.R.K.-Smart-Payment-Analytics-Risk-Kernel/docs/page_copy_spec.md).

### General Copy Patterns Used Across All Pages
- **Buttons name the action, not a generic verb:** `Save changes`, not `Submit`. `Sign in`, not `Login`. `Start simulation`, not `Go`.
- **Errors state what happened + how to fix it**, no apology: `That code expired. Request a new one.` — not `Oops! Something went wrong.`
- **Empty states invite action**, never just say "nothing here": every empty state includes one sentence of context and one next step.
- **Toasts confirm in the same word as the action that triggered them:** `Save changes` → `Changes saved`. `Create account` → `Account created`.
- **Numbers and IDs always render in mono** (per the type system) — transaction IDs, risk scores, ring IDs, timestamps.

---

## 📱 Dashboard Pages & Content Overview

The S.P.A.R.K. dashboard consists of **13 fully implemented pages** organized into primary task flows:

### 1. 📊 Risk Overview (Dashboard Home) — `/` (`app/page.jsx`)
The central command center for merchant risk posture:
* **KPI Metrics**: Scored today, chargeback-confirmed fraud rate, active alerts, and average scoring latency (FastAPI / XGBoost).
* **Decisions by Tier Chart**: 24-hour visual breakdown of Allowed, Challenged, and Blocked transactions.
* **Drift Sparkline**: Real-time Population Stability Index (PSI) sparkline monitoring live score distribution vs. training baseline.
* **Live Feed**: Auto-refreshing feed of incoming transaction scores with risk progress bars and decision badges.
* **Active Abuse Rings Panel**: Summary cards of currently detected fraud clusters with member counts and flagged ₹ amounts.
* **Decision Engine Explainer**: Overview of S.P.A.R.K.'s cost-sensitive 3-tier policy vs binary block/allow systems.

---

### 2. 💳 Transactions Hub — `/transactions` (`app/transactions/page.jsx`)
Full searchable and filterable ledger of every transaction scored by the kernel:
* **Filter Chips**: Quick-filter by risk decision (`All`, `Allowed`, `Challenged`, `Blocked`) with dynamic count indicators.
* **Advanced Search Form**: Search by Transaction ID, User ID/Name, Card BIN, Merchant, Date range, or Risk Score range.
* **Results Data Table**: Displays transaction ID, user details, payment method, risk score bar, decision tier badge, abuse ring indicator, and scoring timestamp.

---

### 3. 🔍 Transaction Deep-Dive — `/transactions/[txn_id]` (`app/transactions/[txn_id]/page.jsx`)
Per-transaction explainability and risk attribution view:
* **Key Stats Header**: Transaction amount, risk score, decision tier, and associated ring membership.
* **SHAP Feature Contribution Chart**: SHAP value contribution bars showing top driving features (e.g. velocity, device reuse, geo mismatch, card BIN risk vs. historical trust).
* **Counterfactual Module**: Plain-language counterfactual explanation detailing what specific threshold or variable change would have flipped the decision.
* **User & Device Context**: User profile, city, device fingerprint, IP address, and card BIN details.
* **Ring Context Card**: Deep link to ring details if the transaction's risk score was elevated due to graph cluster membership.

---

### 4. 📈 Metrics & Cost Curve — `/metrics` (`app/metrics/page.jsx`)
Comprehensive model evaluation panel on the held-out test set:
* **Interactive Cost Curve Chart (Recharts)**: Plots total estimated ₹ cost across decision thresholds for S.P.A.R.K.'s 3-tier system vs. a naive binary block/allow baseline, highlighting optimal savings.
* **Evaluation Methodology**: Documentation on the time-based train/test split, cost-sensitive threshold calibration (1 missed fraud ≈ 8 false positives), and per-tier evaluation rules.
* **Per-Tier Metrics Table**: Reports Precision, Recall, F1 score, and Support separately for Allow, Challenge, and Block tiers, alongside Macro F1.
* **Color-Coded Confusion Matrix**: 3x3 matrix mapping actual fraud labels against predicted tiers with diagonal accuracy highlights.

---

### 5. 🕸️ Abuse Ring Explorer — `/rings` (`app/rings/page.jsx`)
Overview of coordinated fraud clusters detected by the graph layer (Apache AGE / NetworkX):
* **Rings Table**: Displays cluster ID, member account count, shared attribute (device fingerprint, IP subnet, card BIN, shipping address), shared attribute value, graph density %, total flagged ₹ amount, and detection status (`active`, `review`, `contained`).

---

### 6. 🌐 Ring Cluster Detail — `/rings/[ring_id]` (`app/rings/[ring_id]/page.jsx`)
Graph visualization and cluster forensic breakdown:
* **SVG Cluster Graph**: Radial node graph linking the central shared attribute node to perimeter member account nodes with graph edges and glow indicators.
* **Forensic Rationale**: Inferred data insights explaining cluster edge density (e.g., 83% vs 4% cross-merchant baseline), shared attribute value, and velocity anomalies.
* **Member Transactions Table**: Scored attempts originating from any account belonging to the cluster.

---

### 7. 📜 Audit Trail — `/audit` (`app/audit/page.jsx`)
Immutable decision log for regulatory compliance and internal audit:
* **Search & Filters**: Search by Transaction ID or User ID; filter by action (`Allow`, `Challenge`, `Block`) or trigger rule (`Model score`, `Ring membership`, `Velocity spike`, `BIN risk list`).
* **Audit Table**: Full timestamped log showing transaction ID, decision action badge, trigger condition, reasoning text, and compliance export button.

---

### 8. 🛡️ Model Health & Drift Monitor — `/model-health` (`app/model-health/page.jsx`)
Production model performance and Population Stability Index (PSI) tracking:
* **Model Card Details**: XGBoost version, training timeframe, held-out test accuracy (97.8%), macro F1 (0.795), p95 latency (84 ms), and MLflow run ID.
* **30-Day PSI Chart**: SVG line chart tracking daily score drift against Watch (0.05) and Retrain (0.10) thresholds.
* **Feature-Level Drift Table**: Feature drift scores and directional trend arrows (`velocity_1h`, `device_reuse`, `geo_mismatch`, `bin_risk`, `amount_z`) with mitigation notes.

---

### 9. ⚡ Traffic Load Simulation — `/simulation` (`app/simulation/page.jsx`)
Interactive load generator to simulate real-time transaction bursts:
* **Configurable Parameters**: Rate (txns/sec up to 20,000), duration (seconds), and attack scenarios (`Baseline mix`, `Card testing burst`, `Coordinated ring`, `Low-value noise`).
* **Real-time Performance Metrics**: Animated progress bar, total ingested count, p50 / p95 / p99 scoring latency calculations, and live per-tier decision distribution.

---

### 10. ⚙️ Settings & Calibration — `/settings` (`app/settings/page.jsx`)
System configuration and threshold tuning:
* **Appearance Controls**: Theme switcher (`Light`, `Dark`, `System`) with smooth CSS custom property transitions.
* **Integrations**: Razorpay test key ID, read-only API key display, and Slack alert webhook configuration.
* **Decision Threshold Calibrator**: Adjustable Allow & Block score boundaries with automatic Challenge band derivation and instant save feedback.
* **Notification Preferences**: Toggles for abuse ring email alerts and model drift warnings.

---

### 11. 👤 User Profile — `/profile` (`app/profile/page.jsx`)
Risk manager account panel:
* **Profile Details**: Name, email, role (`Senior Fraud Analyst`), merchant affiliation, session status, and security preferences.

---

### 12. 🔐 Authentication Pages — `/login`, `/signup`, `/forgot-password` (`app/...`)
Complete auth workflow templates:
* **Login (`/login`)**: Merchant login form with remember-me and quick navigation.
* **Signup (`/signup`)**: Merchant onboarding form with company details and password setup.
* **Forgot Password (`/forgot-password`)**: Password recovery request workflow.

---

## 🎨 Design System & Aesthetics

* **Theme Architecture**: Built with CSS variables (`styles/tokens.css`) supporting smooth Light Mode, Dark Mode, and System preference matching.
* **Glassmorphism Header**: Backdrop blur sticky navigation with active link pill indicators and instant theme toggling.
* **Typography**: Clean hierarchy using Google Fonts (`Space Grotesk` for headers, `Inter` for body UI, `IBM Plex Mono` for scores, IDs, and code).
* **Micro-animations**: Smooth hover transitions, pulsing live indicators, and progress bar draws.