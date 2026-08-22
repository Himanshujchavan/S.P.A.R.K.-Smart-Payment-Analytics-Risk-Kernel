// Transactions page — full searchable list of every scored transaction
// with filters, score bars, and a counterfactual explainer for every
// Challenged or Blocked decision.

import Link from 'next/link'
import { api } from '../../lib/api'
import { PageHeader, DataTable, ScoreBar, TierBadge, TextInput, Select, Card, Button } from '../../components/Primitives'

const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })
const time = new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit' })

export default async function TransactionsPage({ searchParams }) {
  const sp = await searchParams
  const tier = sp?.tier || 'all'
  const q = sp?.q || ''

  const all = await api.listTransactions()
  const rows = all.filter((t) => {
    if (tier !== 'all' && t.decision !== tier) return false
    if (q) {
      const hay = `${t.id} ${t.userId} ${t.userName} ${t.cardBin}`.toLowerCase()
      if (!hay.includes(q.toLowerCase())) return false
    }
    return true
  })

  const counts = {
    allow: all.filter((t) => t.decision === 'allow').length,
    challenge: all.filter((t) => t.decision === 'challenge').length,
    block: all.filter((t) => t.decision === 'block').length,
  }

  return (
    <div>
      <PageHeader
        title="Transactions"
        subtitle="Every transaction scored by S.P.A.R.K., searchable and filterable."
      />

      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <FilterChip label="All" count={all.length} href="/transactions" active={tier === 'all'} />
        <FilterChip label="Allowed" count={counts.allow} href="/transactions?tier=allow" active={tier === 'allow'} />
        <FilterChip label="Challenged" count={counts.challenge} href="/transactions?tier=challenge" active={tier === 'challenge'} />
        <FilterChip label="Blocked" count={counts.block} href="/transactions?tier=block" active={tier === 'block'} />
      </div>

      <form
        method="GET"
        action="/transactions"
        style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr) auto', gap: 8, marginBottom: 16 }}
      >
        {tier !== 'all' && <input type="hidden" name="tier" value={tier} />}
        <TextInput name="q" defaultValue={q} placeholder="Search by ID, user, or card BIN" />
        <TextInput name="merchant" placeholder="Merchant" />
        <TextInput name="date" type="date" />
        <TextInput name="range" placeholder="Risk score 0–100" />
        <Button type="submit" variant="secondary">Apply</Button>
      </form>

      <Card title={`Results · ${rows.length.toLocaleString('en-IN')}`} subtitle="Most recent first">
        <DataTable
          rows={rows}
          empty="No transactions match these filters"
          columns={[
            { key: 'id', header: 'Transaction', render: (r) => (
              <Link href={`/transactions/${r.id}`} style={{ fontFamily: 'var(--font-mono)' }}>
                {r.id.slice(0, 14)}…
              </Link>
            )},
            { key: 'user', header: 'User', render: (r) => (
              <div>
                <div style={{ color: 'var(--text-primary)' }}>{r.userName}</div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{r.userId}</div>
              </div>
            )},
            { key: 'amount', header: 'Amount', render: (r) => <span style={{ fontFamily: 'var(--font-mono)' }}>{inr.format(r.amount)}</span>, align: 'right' },
            { key: 'method', header: 'Method', render: (r) => (
              <span style={{ textTransform: 'capitalize' }}>{r.method} · {r.cardBin}</span>
            )},
            { key: 'score', header: 'Risk', render: (r) => (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 110 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-secondary)' }}>
                  <span>score</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{(r.riskScore / 100).toFixed(2)}</span>
                </div>
                <ScoreBar value={r.riskScore} />
              </div>
            )},
            { key: 'decision', header: 'Decision', render: (r) => <TierBadge tier={r.decision} /> },
            { key: 'ring', header: 'Ring', render: (r) => r.ringId ? (
              <Link href={`/rings/${r.ringId}`} style={{ color: 'var(--risk-block)', fontFamily: 'var(--font-mono)' }}>⚠ {r.ringId}</Link>
            ) : <span style={{ color: 'var(--text-secondary)' }}>—</span> },
            { key: 'at', header: 'Scored at', render: (r) => <span style={{ fontFamily: 'var(--font-mono)' }}>{time.format(new Date(r.scoredAt))}</span>, nowrap: true },
          ]}
        />
      </Card>
    </div>
  )
}

function FilterChip({ label, count, href, active }) {
  return (
    <Link
      href={href}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '6px 12px',
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 500,
        textDecoration: 'none',
        background: active ? 'var(--navy-primary)' : 'var(--bg-surface)',
        color: active ? '#fff' : 'var(--text-primary)',
        border: '1px solid ' + (active ? 'var(--navy-primary)' : 'var(--border-hairline)'),
      }}
    >
      {label}
      <span style={{
        fontFamily: 'var(--font-mono)',
        color: active ? 'rgba(255,255,255,0.8)' : 'var(--text-secondary)',
      }}>{count}</span>
    </Link>
  )
}
