// Detected abuse rings — list of clusters found by the graph layer.

import Link from 'next/link'
import { api } from '../../lib/api'
import { PageHeader, DataTable } from '../../components/Primitives'

const time = new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0, notation: 'compact' })

export default async function RingsPage() {
  const rings = await api.listRings()

  return (
    <div>
      <PageHeader
        title="Detected abuse rings"
        subtitle="Coordinated activity across accounts, flagged by shared attributes (device, IP, card BIN, or address)."
      />
      <DataTable
        rows={rings}
        empty="No rings detected"
        getRowHref
        columns={[
          { key: 'id', header: 'Ring', render: (r) => (
            <Link href={`/rings/${r.id}`} style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 600 }}>
              {r.id}
            </Link>
          )},
          { key: 'members', header: 'Members', render: (r) => r.memberCount, mono: true, align: 'right' },
          { key: 'shared', header: 'Shared attribute', render: (r) => (
            <div>
              <div style={{ color: 'var(--text-primary)', fontSize: 12 }}>{r.sharedAttribute.replace(/_/g, ' ')}</div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{r.sharedValue}</div>
            </div>
          )},
          { key: 'density', header: 'Density', render: (r) => (
            <span style={{ fontFamily: 'var(--font-mono)' }}>{(r.density * 100).toFixed(0)}%</span>
          ), mono: true, align: 'right' },
          { key: 'flagged', header: 'Flagged', render: (r) => (
            <span style={{ color: 'var(--risk-block)', fontFamily: 'var(--font-mono)' }}>{inr.format(r.flaggedAmount)}</span>
          ), mono: true, align: 'right' },
          { key: 'status', header: 'Status', render: (r) => {
            const colors = {
              active: 'var(--risk-block)',
              review: 'var(--risk-challenge)',
              contained: 'var(--text-secondary)',
            }
            return (
              <span style={{
                fontSize: 11,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: 0.4,
                color: colors[r.status],
              }}>{r.status}</span>
            )
          }},
          { key: 'detected', header: 'Detected', render: (r) => <span style={{ fontFamily: 'var(--font-mono)' }}>{time.format(new Date(r.detectedAt))}</span>, nowrap: true },
        ]}
      />
    </div>
  )
}
