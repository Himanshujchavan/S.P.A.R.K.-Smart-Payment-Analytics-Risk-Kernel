// Single ring detail — graph visualization, member list, shared-attribute
// detail, and the transactions that lifted risk for these accounts.

import Link from 'next/link'
import { notFound } from 'next/navigation'
import { api } from '../../../lib/api'
import RingGraph from '../../../components/RingGraph'
import { PageHeader, Card, DataTable, StatTile, Button, TierBadge } from '../../../components/Primitives'

const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })
const time = new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })

export default async function RingDetailPage({ params }) {
  const { ring_id } = await params
  const rings = await api.listRings()
  const ring = rings.find((r) => r.id === ring_id)
  if (!ring) return notFound()

  const txns = await api.listTransactions()
  const memberTxns = txns.filter((t) => ring.accountIds.includes(t.userId))

  return (
    <div>
      <PageHeader
        title={ring.id}
        subtitle={`${ring.memberCount} accounts sharing ${ring.sharedAttribute.replace(/_/g, ' ')}`}
        actions={<Link href="/rings"><Button variant="secondary">← All rings</Button></Link>}
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
        <StatTile label="Members" value={ring.memberCount.toString()} hint="distinct accounts" />
        <StatTile label="Density" value={(ring.density * 100).toFixed(0) + '%'} hint="graph density score" />
        <StatTile label="Flagged amount" value={inr.format(ring.flaggedAmount)} hint="across all members" trend="up" />
        <StatTile label="Status" value={ring.status} hint={time.format(new Date(ring.detectedAt))} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 16, marginBottom: 20 }}>
        <Card title="Cluster graph" subtitle={`Shared ${ring.sharedAttribute.replace(/_/g, ' ')}: ${ring.sharedValue}`}>
          <RingGraph ring={ring} />
          <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>
            Center node = the shared attribute. Each perimeter node is a member account. Edges
            represent the graph link. The production graph layer (Apache AGE / NetworkX)
            computes Louvain communities on shared-attribute edges every 5 minutes.
          </p>
        </Card>
        <Card title="Why this is a ring" subtitle="Inferred from the data">
          <ul style={{ margin: 0, paddingLeft: 18, color: 'var(--text-primary)', fontSize: 13, lineHeight: 1.6 }}>
            <li>{ring.memberCount} distinct user accounts share <code style={{ fontFamily: 'var(--font-mono)' }}>{ring.sharedValue}</code> as their {ring.sharedAttribute.replace(/_/g, ' ')}.</li>
            <li>Edge density inside the cluster is <strong>{(ring.density * 100).toFixed(0)}%</strong> — substantially higher than the cross-merchant baseline of ~4%.</li>
            <li>Combined flagged amount in the last 30 days: <strong style={{ color: 'var(--risk-block)' }}>{inr.format(ring.flaggedAmount)}</strong>.</li>
            <li>Transactions across these accounts exhibit velocity patterns consistent with card-testing (many small-ticket attempts) and synthetic identities (low historical-good scores).</li>
          </ul>
        </Card>
      </div>

      <Card title="Recent transactions across members" subtitle="Latest scored attempts from any member of this ring">
        <DataTable
          rows={memberTxns}
          empty="No recent member transactions"
          columns={[
            { key: 'id', header: 'Transaction', render: (r) => (
              <Link href={`/transactions/${r.id}`} style={{ fontFamily: 'var(--font-mono)' }}>{r.id.slice(0, 14)}…</Link>
            )},
            { key: 'user', header: 'User', render: (r) => r.userId, mono: true },
            { key: 'amount', header: 'Amount', render: (r) => <span style={{ fontFamily: 'var(--font-mono)' }}>{inr.format(r.amount)}</span>, mono: true, align: 'right' },
            { key: 'score', header: 'Score', render: (r) => (r.riskScore / 100).toFixed(2), mono: true, align: 'right' },
            { key: 'decision', header: 'Decision', render: (r) => <TierBadge tier={r.decision} /> },
            { key: 'at', header: 'When', render: (r) => <span style={{ fontFamily: 'var(--font-mono)' }}>{time.format(new Date(r.scoredAt))}</span>, nowrap: true },
          ]}
        />
      </Card>
    </div>
  )
}
