// Live transaction feed — auto-refreshing list of recent S.P.A.R.K. decisions
// with score bars, tier badges, and the counterfactual explanation for
// every Challenged or Blocked transaction.

'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { api } from '../lib/api'
import { Card, TierBadge, ScoreBar } from './Primitives'

const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })
const time = new Intl.DateTimeFormat('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

export default function TransactionFeed({ limit = 12, refreshMs = 5000, showHeader = true }) {
  const [txns, setTxns] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    const load = () =>
      api.listTransactions({ limit }).then((data) => {
        if (!alive) return
        setTxns(data.slice(0, limit))
        setLoading(false)
        setError(null)
      }).catch((err) => { if (alive) { setError(err.message); setLoading(false) } })
    load()
    const id = setInterval(load, refreshMs)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [limit, refreshMs])

  return (
    <Card
      title="Live transaction feed"
      subtitle="Auto-refreshing · every decision S.P.A.R.K. makes is logged"
      action={
        <span
          style={{
            fontSize: 11,
            color: 'var(--text-secondary)',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: 999,
              background: 'var(--risk-allow)',
              boxShadow: '0 0 0 0 color-mix(in srgb, var(--risk-allow) 50%, transparent)',
              animation: 'spark-pulse 1.6s infinite',
            }}
          />
          LIVE
        </span>
      }
    >
      <style>{`@keyframes spark-pulse { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--risk-allow) 50%, transparent); } 70% { box-shadow: 0 0 0 6px transparent; } 100% { box-shadow: 0 0 0 0 transparent; } }`}</style>
      {error ? (<p style={{color:'var(--risk-block)',fontSize:13,margin:0}}>Unable to load recent decisions: {error}</p>) : loading ? (
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, margin: 0 }}>Loading recent decisions…</p>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {txns.map((t) => (
            <li
              key={t.id}
              style={{
                display: 'grid',
                gridTemplateColumns: '1.2fr 0.8fr 1fr 0.8fr 0.8fr',
                gap: 12,
                alignItems: 'center',
                padding: '10px 12px',
                background: 'var(--bg-surface)',
                borderRadius: 6,
                border: '1px solid var(--border-hairline)',
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Link
                    href={`/transactions/${t.id}`}
                    style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontSize: 12 }}
                  >
                    {t.id.slice(0, 12)}…
                  </Link>
                  <TierBadge tier={t.decision} />
                </div>
                <div style={{ color: 'var(--text-secondary)', fontSize: 11, marginTop: 2 }}>
                  {t.userName} · {t.city} · {t.method}
                </div>
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>{inr.format(t.amount)}</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-secondary)' }}>
                  <span>risk score</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{(t.riskScore / 100).toFixed(2)}</span>
                </div>
                <ScoreBar value={t.riskScore} />
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                {t.ringId ? (
                  <Link href={`/rings/${t.ringId}`} style={{ color: 'var(--risk-block)', fontWeight: 600 }}>
                    ⚠ {t.ringId}
                  </Link>
                ) : (
                  <span>—</span>
                )}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                {time.format(new Date(t.scoredAt))}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
