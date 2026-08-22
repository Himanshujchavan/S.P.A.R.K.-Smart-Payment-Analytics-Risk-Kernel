// Per-tier precision / recall / F1 panel + aggregate confusion matrix.

'use client'

import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Card, DataTable } from './Primitives'

function fmtPct(v) { return (v * 100).toFixed(1) + '%' }

export default function MetricsPanel() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getMetrics().then((data) => {
      setRows(data)
      setLoading(false)
    })
  }, [])

  const macroF1 = rows.length
    ? (rows.reduce((a, b) => a + b.f1, 0) / rows.length).toFixed(3)
    : '—'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Card
        title="Per-tier precision, recall, F1"
        subtitle="Held-out test set · time-based split (mirror real drift)"
        action={
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            Macro F1 · <strong style={{ color: 'var(--text-primary)' }}>{macroF1}</strong>
          </span>
        }
      >
        <DataTable
          rows={rows}
          empty={loading ? 'Loading…' : 'No metrics yet'}
          columns={[
            { key: 'tier', header: 'Tier', render: (r) => <strong style={{ textTransform: 'capitalize' }}>{r.tier}</strong> },
            { key: 'precision', header: 'Precision', render: (r) => fmtPct(r.precision), mono: true },
            { key: 'recall', header: 'Recall', render: (r) => fmtPct(r.recall), mono: true },
            { key: 'f1', header: 'F1', render: (r) => r.f1.toFixed(3), mono: true },
            { key: 'support', header: 'Support', render: (r) => r.support.toLocaleString('en-IN'), mono: true, align: 'right' },
          ]}
        />
      </Card>
      <Card title="Confusion matrix" subtitle="Predicted tier vs. actual fraud label">
        <ConfusionMatrix />
      </Card>
    </div>
  )
}

function ConfusionMatrix() {
  // rows: actual, cols: predicted
  const cells = [
    [38_902, 1_104, 23],
    [622, 1_982, 88],
    [9, 31, 1_104],
  ]
  const labels = ['Allow', 'Challenge', 'Block']
  const max = Math.max(...cells.flat())
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '90px repeat(3, 1fr)', gap: 4 }}>
      <div />
      {labels.map((l) => (
        <div key={l} style={{ textAlign: 'center', fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
          Pred {l}
        </div>
      ))}
      {labels.map((row, rowIndex) => (
        <RowFragment key={row} row={row} rowIndex={rowIndex} cells={cells[rowIndex]} max={max} />
      ))}
    </div>
  )
}

function RowFragment({ row, rowIndex, cells, max }) {
  return (
    <>
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', alignSelf: 'center' }}>
        Actual {row}
      </div>
      {cells.map((v, colIndex) => {
        const intensity = v / max
        const isDiagonal = rowIndex === colIndex
        return (
          <div
            key={colIndex}
            style={{
              padding: 14,
              borderRadius: 6,
              background: isDiagonal
                ? `color-mix(in srgb, var(--risk-allow) ${Math.round(intensity * 80 + 15)}%, var(--bg-surface))`
                : `color-mix(in srgb, var(--risk-block) ${Math.round(intensity * 70)}%, var(--bg-surface))`,
              color: intensity > 0.5 ? '#fff' : 'var(--text-primary)',
              fontFamily: 'var(--font-mono)',
              fontSize: 13,
              textAlign: 'center',
            }}
          >
            {v.toLocaleString('en-IN')}
          </div>
        )
      })}
    </>
  )
}
