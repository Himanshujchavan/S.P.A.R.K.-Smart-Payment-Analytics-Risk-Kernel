// Model health — current model card, PSI over time, feature-level drift.

import { api } from '../../lib/api'
import { PageHeader, Card, DataTable } from '../../components/Primitives'

const time = new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short' })

export default async function ModelHealthPage() {
  const health = await api.getModelHealth();
  const drift = health.psi || [];
  const featureDrift = health.feature_drift || [];
  const currentPsi = drift[drift.length - 1]?.psi || 0;
  const status = currentPsi > 0.1 ? 'high' : currentPsi > 0.05 ? 'watch' : 'stable';

  return (
    <div>
      <PageHeader
        title="Model health"
        subtitle="How the current production model is performing against live traffic."
      />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
        <Card title="Current model" subtitle="Production-deployed XGBoost classifier">
          <dl style={{ display: 'grid', gridTemplateColumns: '160px 1fr', rowGap: 8, columnGap: 12, margin: 0, fontSize: 13 }}>
            <dt style={{ color: 'var(--text-secondary)' }}>Version</dt>
            <dd style={{ margin: 0, fontFamily: 'var(--font-mono)' }}>{health.model.version}</dd>
            <dt style={{ color: 'var(--text-secondary)' }}>Trained on</dt>
            <dd style={{ margin: 0 }}>{health.model.trained_on}</dd>
            <dt style={{ color: 'var(--text-secondary)' }}>Deployed</dt>
            <dd style={{ margin: 0 }}>{health.model.last_retrained}</dd>
            <dt style={{ color: 'var(--text-secondary)' }}>Held-out test accuracy</dt>
            <dd style={{ margin: 0, fontFamily: 'var(--font-mono)' }}>{(health.model.accuracy * 100).toFixed(1)}%</dd>
            <dt style={{ color: 'var(--text-secondary)' }}>Macro F1</dt>
            <dd style={{ margin: 0, fontFamily: 'var(--font-mono)' }}>{health.model.macro_f1}</dd>
            <dt style={{ color: 'var(--text-secondary)' }}>Current Status</dt>
            <dd style={{ margin: 0, fontWeight: 600, color: 'var(--accent-spark)' }}>{health.model.current_drift_status}</dd>
            <dt style={{ color: 'var(--text-secondary)' }}>MLflow run</dt>
            <dd style={{ margin: 0, fontFamily: 'var(--font-mono)' }}>{health.model.mlflow_run_id || '—'}</dd>
          </dl>
        </Card>

        <Card
          title="Population stability index (PSI)"
          subtitle="Live traffic vs. training baseline · last 30 days"
          action={<DriftBadge status={status} value={currentPsi} />}
        >
          <DriftChart data={drift} />
          <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>
            PSI compares the live score distribution against the training distribution. &lt; 0.05 is
            stable, 0.05–0.1 warrants a watch, &gt; 0.1 means fraud patterns are shifting and the
            model should be retrained on recent labeled data.
          </p>
        </Card>
      </div>

      <Card title="Feature-level drift" subtitle="Top features by drift score this week">
        <DataTable
          rows={featureDrift}
          empty="No drift detected"
          columns={[
            { key: 'feature', header: 'Feature', render: (r) => (
              <code style={{ fontFamily: 'var(--font-mono)' }}>{r.feature}</code>
            )},
            { key: 'score', header: 'Drift score', render: (r) => (
              <span style={{ fontFamily: 'var(--font-mono)' }}>{r.score.toFixed(2)}</span>
            ), mono: true, align: 'right' },
            { key: 'trend', header: 'Trend', render: (r) => {
              const colors = { up: 'var(--risk-block)', down: 'var(--risk-allow)', flat: 'var(--text-secondary)' }
              const glyphs = { up: '▲', down: '▼', flat: '→' }
              return <span style={{ color: colors[r.trend], fontFamily: 'var(--font-mono)' }}>{glyphs[r.trend]} {r.trend}</span>
            }},
            { key: 'note', header: 'Notes', render: (r) => (
              <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>
                {r.feature === 'velocity_1h' && 'Bursty card-testing waves; consider trimming long tail.'}
                {r.feature === 'device_reuse' && 'Synthetic identity farms sharing Android emulator fingerprints.'}
                {r.feature === 'geo_mismatch' && 'New region traffic from existing good accounts.'}
                {r.feature === 'bin_risk' && 'Stable. The risk list refreshes nightly.'}
                {r.note || ''}
              </span>
            )},
          ]}
        />
      </Card>
    </div>
  )
}

function DriftBadge({ status, value }) {
  const colors = { stable: 'var(--risk-allow)', watch: 'var(--risk-challenge)', high: 'var(--risk-block)' }
  const labels = { stable: 'Stable', watch: 'Watch', high: 'Drift detected' }
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '2px 10px', borderRadius: 999, fontSize: 11, fontWeight: 600,
      background: 'color-mix(in srgb, ' + colors[status] + ' 15%, transparent)',
      color: colors[status],
      border: '1px solid color-mix(in srgb, ' + colors[status] + ' 35%, transparent)',
    }}>
      <span style={{ width: 6, height: 6, borderRadius: 999, background: colors[status] }} />
      {labels[status]} · {value.toFixed(3)}
    </span>
  )
}

function DriftChart({ data }) {
  if (!data.length) return null
  const w = 560, h = 140, pad = 24
  const max = Math.max(0.12, ...data.map((d) => d.psi))
  const points = data
    .map((d, i) => {
      const x = pad + (data.length === 1 ? 0.5 : i / (data.length - 1)) * (w - pad * 2)
      const y = h - pad - (d.psi / max) * (h - pad * 2)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  const area = points + ` ${w - pad},${h - pad} ${pad},${h - pad}`
  const watchY = h - pad - (0.05 / max) * (h - pad * 2)
  const driftY = h - pad - (0.1 / max) * (h - pad * 2)

  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 160 }} role="img" aria-label="PSI chart">
        <polygon fill="var(--accent-spark)" fillOpacity="0.12" points={area} />
        <line x1={pad} y1={driftY} x2={w - pad} y2={driftY} stroke="var(--risk-block)" strokeOpacity="0.5" strokeDasharray="4 4" />
        <text x={w - pad} y={driftY - 4} textAnchor="end" fontSize="9" fill="var(--risk-block)">retrain threshold 0.10</text>
        <line x1={pad} y1={watchY} x2={w - pad} y2={watchY} stroke="var(--risk-challenge)" strokeOpacity="0.5" strokeDasharray="4 4" />
        <text x={w - pad} y={watchY - 4} textAnchor="end" fontSize="9" fill="var(--risk-challenge)">watch 0.05</text>
        <polyline fill="none" stroke="var(--accent-spark)" strokeWidth="2" points={points} />
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-secondary)', marginTop: -4 }}>
        <span>{time.format(new Date(data[0].date))}</span>
        <span>{time.format(new Date(data[data.length - 1].date))}</span>
      </div>
    </div>
  )
}
