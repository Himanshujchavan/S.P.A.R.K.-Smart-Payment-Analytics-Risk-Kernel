// Audit trail viewer — every decision, with its trigger and reasoning,
// filterable by action and triggered-by rule.

'use client'

import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { Card, DataTable, TextInput, Select, TierBadge, Button } from './Primitives'

const time = new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit' })

export default function AuditTrailViewer() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [action, setAction] = useState('all')
  const [trigger, setTrigger] = useState('all')

  useEffect(() => {
    api.listAudit().then((d) => {
      setRows(d)
      setLoading(false)
    })
  }, [])

  const triggers = useMemo(() => ['all', ...Array.from(new Set(rows.map((r) => r.triggeredBy)))], [rows])

  const filtered = rows.filter((r) => {
    if (action !== 'all' && r.action !== action) return false
    if (trigger !== 'all' && r.triggeredBy !== trigger) return false
    if (q && !`${r.transactionId} ${r.user}`.toLowerCase().includes(q.toLowerCase())) return false
    return true
  })

  return (
    <Card
      title="Audit trail"
      subtitle="Every decision, with its trigger and the reasoning that produced it"
      action={
        <Button
          variant="secondary"
          onClick={() => alert('Export queued — entries above will be sent to your compliance inbox.')}
        >
          Export for compliance
        </Button>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 160px 200px', gap: 8, marginBottom: 12 }}>
        <TextInput
          placeholder="Search by transaction ID or user…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <Select value={action} onChange={(e) => setAction(e.target.value)}>
          <option value="all">All actions</option>
          <option value="allow">Allow</option>
          <option value="challenge">Challenge</option>
          <option value="block">Block</option>
        </Select>
        <Select value={trigger} onChange={(e) => setTrigger(e.target.value)}>
          {triggers.map((t) => (
            <option key={t} value={t}>
              {t === 'all' ? 'All triggers' : t}
            </option>
          ))}
        </Select>
      </div>
      <DataTable
        rows={filtered}
        empty={loading ? 'Loading audit entries…' : 'No audit entries in this range'}
        columns={[
          { key: 'timestamp', header: 'Timestamp', render: (r) => time.format(new Date(r.timestamp)), mono: true },
          { key: 'transactionId', header: 'Transaction', render: (r) => r.transactionId.slice(0, 14) + '…', mono: true },
          { key: 'action', header: 'Action', render: (r) => <TierBadge tier={r.action} /> },
          { key: 'triggeredBy', header: 'Triggered by' },
          { key: 'reasoning', header: 'Reasoning', render: (r) => <span style={{ color: 'var(--text-secondary)' }}>{r.reasoning}</span> },
        ]}
      />
    </Card>
  )
}
