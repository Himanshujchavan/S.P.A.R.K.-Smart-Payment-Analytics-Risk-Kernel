// Dashboard home — at-a-glance risk health for the merchant:
// KPI tiles, decisions-by-tier chart, live feed, drift and ring panels.

import Link from 'next/link'
import TransactionFeed from '../components/TransactionFeed'
import { api } from '../lib/api'
import { PageHeader, StatTile, Card, Button } from '../components/Primitives'
import { TIER_META } from '../lib/types'

export default async function HomePage() {
  const [kpis, rings, health] = await Promise.all([
    api.getDashboardKpis(),
    api.listRings(),
    api.getModelHealth(),
  ])

  const drift = health.psi || []
  const total = kpis.tierBreakdown.allow + kpis.tierBreakdown.challenge + kpis.tierBreakdown.block
  const currentPsi = drift.length ? drift[drift.length - 1].psi : 0
  const driftStatus = currentPsi > 0.1 ? 'high' : currentPsi > 0.05 ? 'watch' : 'stable'

  return (
    <div>
      <PageHeader
        title="Risk overview"
        subtitle="Live decisions, drift status, and active abuse rings across your Razorpay transactions."
        actions={
          <>
            <Link href="/simulation"><Button variant="secondary">Run simulation</Button></Link>
            <Link href="/metrics"><Button>View metrics</Button></Link>
          </>
        }
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
        <StatTile
          label="Scored today"
          value={kpis.scoredToday.toLocaleString('en-IN')}
          delta="+8.4% vs yesterday"
          trend="up"
          hint="across 14 merchants"
        />
        <StatTile
          label="Fraud rate"
          value={(kpis.fraudRate * 100).toFixed(2) + '%'}
          delta="−0.6 pts"
          trend="down"
          hint="chargeback-confirmed"
        />
        <StatTile
          label="Active alerts"
          value={kpis.activeAlerts.toString()}
          delta={kpis.activeAlerts > 0 ? 'action needed' : 'all clear'}
          trend={kpis.activeAlerts > 0 ? 'down' : 'flat'}
        />
        <StatTile
          label="Avg. scoring latency"
          value={kpis.avgLatencyMs + ' ms'}
          delta="p95 84 ms"
          trend="flat"
          hint="FastAPI / XGBoost"
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 16, marginBottom: 20 }}>
        <Card
          title="Decisions by tier — last 24 hours"
          subtitle={`${total.toLocaleString('en-IN')} transactions scored`}
        >
          <DecisionsTierBars breakdown={kpis.tierBreakdown} total={total} />
        </Card>
        <Card
          title="Drift monitor"
          subtitle="Population Stability Index (PSI) vs. training baseline"
          action={
            <DriftStatusBadge status={driftStatus} value={currentPsi} />
          }
        >
          <DriftSparkline data={drift} />
          <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)' }}>
            Live score distribution vs. training baseline. PSI &lt; 0.05 is stable; 0.05–0.1 warrants a
            watch; above 0.1 means fraud patterns are shifting and a retrain is recommended.
          </p>
        </Card>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16, marginBottom: 20 }}>
        <TransactionFeed limit={10} />
        <Card
          title="Active abuse rings"
          subtitle={`${rings.length} clusters under monitoring`}
          action={<Link href="/rings" style={{ fontSize: 12 }}>View all →</Link>}
        >
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {rings.map((r) => (
              <li
                key={r.id}
                style={{
                  padding: 12,
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border-hairline)',
                  borderRadius: 6,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Link href={`/rings/${r.id}`} style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: 13 }}>
                    {r.id}
                  </Link>
                  <span
                    style={{
                      fontSize: 10,
                      textTransform: 'uppercase',
                      letterSpacing: 0.4,
                      color:
                        r.status === 'active'
                          ? 'var(--risk-block)'
                          : r.status === 'review'
                          ? 'var(--risk-challenge)'
                          : 'var(--text-secondary)',
                      fontWeight: 600,
                    }}
                  >
                    {r.status}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                  {r.memberCount} accounts · shared {r.sharedAttribute.replace(/_/g, ' ')}
                </div>
                <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 11, color: 'var(--text-secondary)' }}>
                  <span>Density <strong style={{ color: 'var(--text-primary)' }}>{(r.density * 100).toFixed(0)}%</strong></span>
                  <span>Flagged <strong style={{ color: 'var(--risk-block)', fontFamily: 'var(--font-mono)' }}>₹{r.flaggedAmount.toLocaleString('en-IN')}</strong></span>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card
        title="How S.P.A.R.K. decides"
        subtitle="A three-tier decision engine — not a binary cutoff"
      >
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
          {['allow', 'challenge', 'block'].map((t) => (
            <div
              key={t}
              style={{
                padding: 14,
                borderRadius: 6,
                border: '1px solid color-mix(in srgb, ' + TIER_META[t].color + ' 30%, transparent)',
                background: 'color-mix(in srgb, ' + TIER_META[t].color + ' 6%, var(--bg-surface))',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: 999,
                    background: TIER_META[t].color,
                  }}
                />
                <strong style={{ color: TIER_META[t].color, fontSize: 13 }}>{TIER_META[t].label}</strong>
              </div>
              <p style={{ margin: '6px 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>
                {t === 'allow' &&
                  'Score well below the Challenge band. The transaction proceeds and contributes to the user\'s trust profile.'}
                {t === 'challenge' &&
                  'Score in the medium-risk band. A lightweight step-up (OTP / biometrics) is requested instead of an outright block, reducing false-positive cost.'}
                {t === 'block' &&
                  'Score above the Block threshold, or score lifted by ring membership / velocity spike. The transaction is declined and logged for review.'}
              </p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

function DecisionsTierBars({ breakdown, total }) {
  const tiers = /** @type {const} */ (['allow', 'challenge', 'block'])
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {tiers.map((t) => {
        const count = breakdown[t]
        const pct = total ? (count / total) * 100 : 0
        return (
          <div key={t}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
              <span style={{ color: 'var(--text-primary)', fontWeight: 500, textTransform: 'capitalize' }}>{TIER_META[t].label}</span>
              <span style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                {count.toLocaleString('en-IN')} · {pct.toFixed(1)}%
              </span>
            </div>
            <div style={{ height: 10, background: 'var(--border-hairline)', borderRadius: 999, overflow: 'hidden' }}>
              <div
                style={{
                  width: pct + '%',
                  height: '100%',
                  background: TIER_META[t].color,
                  transition: 'width var(--chart-draw-duration) var(--page-trans-ease)',
                }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}

function DriftStatusBadge({ status, value }) {
  const colors = {
    stable: 'var(--risk-allow)',
    watch: 'var(--risk-challenge)',
    high: 'var(--risk-block)',
  }
  const labels = { stable: 'Stable', watch: 'Watch', high: 'Drift detected' }
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '2px 10px',
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 600,
        background: 'color-mix(in srgb, ' + colors[status] + ' 15%, transparent)',
        color: colors[status],
        border: '1px solid color-mix(in srgb, ' + colors[status] + ' 35%, transparent)',
      }}
    >
      <span style={{ width: 6, height: 6, borderRadius: 999, background: colors[status] }} />
      {labels[status]} · {value.toFixed(3)}
    </span>
  )
}

function DriftSparkline({ data }) {
  if (!data || data.length === 0) return null
  const w = 360, h = 60, pad = 4
  const max = Math.max(0.1, ...data.map((d) => d.psi))
  const points = data
    .map((d, i) => {
      const x = pad + (i / (data.length - 1)) * (w - pad * 2)
      const y = h - pad - (d.psi / max) * (h - pad * 2)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  const baselineY = h - pad - (0.05 / max) * (h - pad * 2)
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 60 }} aria-label="PSI sparkline">
      <line x1={pad} y1={baselineY} x2={w - pad} y2={baselineY} stroke="var(--risk-challenge)" strokeDasharray="3 3" strokeOpacity="0.6" />
      <polyline fill="none" stroke="var(--accent-spark)" strokeWidth="1.8" points={points} />
    </svg>
  )
}
