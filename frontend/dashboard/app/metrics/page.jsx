// Metrics & evaluation page — combines the per-tier metrics panel,
// the cost-curve chart, and a written explanation of the evaluation
// methodology (time-based split, cost-sensitive thresholds).

import MetricsPanel from '../../components/MetricsPanel'
import CostCurveChart from '../../components/CostCurveChart'
import { PageHeader, Card } from '../../components/Primitives'

export default function MetricsPage() {
  return (
    <div>
      <PageHeader
        title="Metrics & evaluation"
        subtitle="Performance on the held-out test set — the numbers behind every decision."
      />
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16, marginBottom: 20 }}>
        <CostCurveChart />
        <Card title="About this evaluation" subtitle="How these numbers were produced">
          <div style={{ fontSize: 13, color: 'var(--text-primary)', display: 'flex', flexDirection: 'column', gap: 10 }}>
            <p style={{ margin: 0 }}>
              <strong>Time-based split.</strong> Trained on transactions from
              <code style={{ fontFamily: 'var(--font-mono)' }}> 2025-08-01</code> to
              <code style={{ fontFamily: 'var(--font-mono)' }}> 2026-07-15</code>. Tested on a held-out
              window from <code style={{ fontFamily: 'var(--font-mono)' }}>2026-07-16</code> to
              <code style={{ fontFamily: 'var(--font-mono)' }}> 2026-08-21</code> the model never saw during
              training. This mirrors the way fraud patterns actually drift in production — random splits
              would be too optimistic.
            </p>
            <p style={{ margin: 0 }}>
              <strong>Cost-sensitive calibration.</strong> Thresholds are tuned to minimize the total
              expected cost across false positives (lost legitimate orders), false negatives (chargeback
              loss), and Challenge friction (one-time OTP success). We weight a missed fraud case at 8×
              a wrongly-blocked legitimate one — derived from your merchant profile.
            </p>
            <p style={{ margin: 0 }}>
              <strong>Per-tier reporting.</strong> We report precision, recall, and F1 separately for
              each of the three tiers so you can see where the model is conservative vs. aggressive, and
              tune the Challenge band as your business risk tolerance shifts.
            </p>
            <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: 12 }}>
              The cost-curve chart to the left shows total ₹ cost across Block-threshold values for
              S.P.A.R.K.'s three-tier decisioning vs. a naive binary block/allow baseline. The optimal
              three-tier configuration recovers a substantial share of the false-positive cost.
            </p>
          </div>
        </Card>
      </div>
      <MetricsPanel />
    </div>
  )
}
