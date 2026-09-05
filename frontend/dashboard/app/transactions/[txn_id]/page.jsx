// Per-transaction detail page — full feature breakdown, score trajectory,
// counterfactual explanation, and the audit entry that recorded the decision.

import Link from 'next/link'
import { api } from '../../../lib/api'
import { PageHeader, Card, TierBadge, ScoreBar, Button, StatTile } from '../../../components/Primitives'
import { TIER_META } from '../../../lib/types'

const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })
const dt = new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })

const FEATURE_DEFS = {
  velocity_1h: { name: 'Velocity (1h)', desc: 'Number of transactions in the past hour, peer group adjusted.' },
  device_reuse: { name: 'Device reuse', desc: 'How many other accounts are seen on this device fingerprint.' },
  bin_risk: { name: 'Card BIN risk', desc: 'Historical chargeback rate for this card BIN.' },
  geo_mismatch: { name: 'Geo mismatch', desc: 'Distance between billing IP geo and the account\'s typical geo.' },
  new_device: { name: 'New device', desc: 'First time this device is seen on a previously established account.' },
  amount_z: { name: 'Amount z-score', desc: 'How unusual the amount is for this user\'s history.' },
  historical_good: { name: 'Historical good', desc: 'Long-term trust score built from past successful transactions.' },
}

export default async function TransactionDetailPage({ params }) {
  const { txn_id } = await params
  const txn = await api.getTransaction(txn_id)
  if (!txn) {
    return (
      <div>
        <PageHeader title="Transaction not found" subtitle={`No record for ${txn_id}.`} />
        <Link href="/transactions"><Button variant="secondary">← Back to transactions</Button></Link>
      </div>
    )
  }
  const ring = txn.ringId ? (await api.listRings()).find((r) => r.id === txn.ringId) : null

  // Guard against a decision value that isn't (yet) present in TIER_META,
  // rather than letting the lookup crash the whole page. The backend now
  // normalizes unscored transactions to 'pending', but this stays as a
  // safety net for any future/unmapped value.
  const tierInfo = TIER_META[txn.decision] ?? { label: txn.decision ?? 'Unknown' }

  return (
    <div>
      <PageHeader
        title={txn.id}
        subtitle={dt.format(new Date(txn.scoredAt))}
        actions={
          <>
            <TierBadge tier={txn.decision} />
            <Link href="/transactions"><Button variant="secondary">← All transactions</Button></Link>
          </>
        }
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
        <StatTile label="Amount" value={inr.format(txn.amount)} hint={txn.method} />
        <StatTile label="Risk score" value={(txn.riskScore / 100).toFixed(2)} hint="XGBoost v2.4.1" />
        <StatTile
          label="Decision"
          value={tierInfo.label}
          hint={`threshold ${
            txn.decision === 'block' ? '≥ 0.78' :
            txn.decision === 'challenge' ? '0.45–0.78' :
            txn.decision === 'allow' ? '< 0.45' :
            txn.decision === 'pending' ? 'not yet scored' :
            'unknown'
          }`}
        />
        <StatTile label="Ring membership" value={txn.ringId || '—'} hint={ring ? `${ring.memberCount} accounts` : 'no cluster'} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16, marginBottom: 20 }}>
        <Card title="Top contributing features" subtitle="What drove this decision (SHAP values)">
          <ScoreBar value={txn.riskScore} />
          <ul style={{ listStyle: 'none', padding: 0, margin: '12px 0 0', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {(txn.topFeatures || []).map((f) => {
              const def = FEATURE_DEFS[f] || { name: f, desc: '' }
              const contribution = typeof f === 'object' && f !== null ? Number(f.shap_value || 0) : 0
              return (
                <li
                  key={f}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '160px 1fr 60px',
                    gap: 12,
                    alignItems: 'center',
                    padding: 10,
                    background: 'var(--bg-surface)',
                    borderRadius: 6,
                  }}
                >
                  <div>
                    <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 }}>{def.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{def.desc}</div>
                  </div>
                  <div style={{ height: 8, background: 'var(--border-hairline)', borderRadius: 999, overflow: 'hidden' }}>
                    <div
                      style={{
                        width: Math.abs(contribution) * 100 + '%',
                        height: '100%',
                        background: contribution < 0 ? 'var(--risk-allow)' : 'var(--risk-block)',
                        marginLeft: contribution < 0 ? (1 + contribution) * 100 + '%' : 0,
                      }}
                    />
                  </div>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, textAlign: 'right', color: contribution < 0 ? 'var(--risk-allow)' : 'var(--risk-block)' }}>
                    {contribution > 0 ? '+' : ''}{contribution.toFixed(2)}
                  </span>
                </li>
              )
            })}
          </ul>
        </Card>

        <Card title="Counterfactual" subtitle="What would have flipped this decision">
          {txn.counterfactual ? (
            <p style={{ margin: 0, fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5 }}>
              {txn.counterfactual}
            </p>
          ) : (
            <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)' }}>
              No flip needed — this decision was on the well-allow side of the band.
            </p>
          )}
          <hr style={{ border: 'none', borderTop: '1px solid var(--border-hairline)', margin: '12px 0' }} />
          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            <div><strong>User:</strong> {txn.userName} ({txn.userId})</div>
            <div><strong>City:</strong> {txn.city}</div>
            <div><strong>Device:</strong> <span style={{ fontFamily: 'var(--font-mono)' }}>{txn.deviceFingerprint}</span></div>
            <div><strong>IP:</strong> <span style={{ fontFamily: 'var(--font-mono)' }}>{txn.ipAddress}</span></div>
            <div><strong>Card BIN:</strong> <span style={{ fontFamily: 'var(--font-mono)' }}>{txn.cardBin}</span></div>
          </div>
        </Card>
      </div>

      {ring && (
        <Card
          title={`Ring context · ${ring.id}`}
          subtitle={`${ring.memberCount} accounts sharing ${ring.sharedAttribute.replace(/_/g, ' ')}`}
        >
          <p style={{ margin: 0, color: 'var(--text-primary)', fontSize: 13 }}>
            This transaction was scored with a +0.12 risk boost because the user belongs to
            ring <strong>{ring.id}</strong>, a cluster of <strong>{ring.memberCount}</strong> accounts
            sharing the same {ring.sharedAttribute.replace(/_/g, ' ')}{' '}
            (<code style={{ fontFamily: 'var(--font-mono)' }}>{ring.sharedValue}</code>).
            Total amount flagged: <strong style={{ color: 'var(--risk-block)' }}>₹{ring.flaggedAmount.toLocaleString('en-IN')}</strong>.
          </p>
          <div style={{ marginTop: 12 }}>
            <Link href={`/rings/${ring.id}`}><Button variant="secondary">Open ring →</Button></Link>
          </div>
        </Card>
      )}
    </div>
  )
}