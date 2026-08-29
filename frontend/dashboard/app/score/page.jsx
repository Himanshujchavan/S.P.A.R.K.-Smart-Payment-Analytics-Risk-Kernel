// frontend/dashboard/app/score/page.jsx
// Scoring view – submit a transaction payload, receive tier decision, SHAP chart, and counterfactual suggestion.

'use client'

import { useState } from 'react'
import { api } from '../../lib/api'
import { PageHeader, Card, Button, StatTile, TierBadge } from '../../components/Primitives'
import { TIER_META } from '../../lib/types'

// Simple SHAP bar chart – displays top‑K features with contribution values.
function ShapBarChart({ features }) {
  if (!features || features.length === 0) return null
  const maxAbs = Math.max(...features.map((f) => Math.abs(f.value)), 0.01)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {features.map((f, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <code style={{ fontFamily: 'var(--font-mono)', width: 120 }}>{f.feature}</code>
          <div style={{ flex: 1, background: 'var(--border-hairline)', height: 8, borderRadius: 4, overflow: 'hidden' }}>
            <div
              style={{
                width: `${(Math.abs(f.value) / maxAbs) * 100}%`,
                height: '100%',
                background: f.value >= 0 ? 'var(--risk-block)' : 'var(--risk-allow)',
                transition: 'width var(--counter-duration) var(--page-trans-ease)',
              }}
            />
          </div>
          <code style={{ fontFamily: 'var(--font-mono)', width: 40, textAlign: 'right' }}>
            {f.value.toFixed(2)}
          </code>
        </div>
      ))}
    </div>
  )
}

export default function ScorePage() {
  const [payload, setPayload] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    try {
      const json = JSON.parse(payload)
      const resp = await api.scoreTransaction(json)
      setResult(resp)
    } catch (e) {
      setError('Invalid JSON or request failed')
    }
    setLoading(false)
  }

  return (
    <div>
      <PageHeader title="Score a transaction" subtitle="Submit raw transaction data and view the three‑tier decision, SHAP feature contributions, and counterfactual recommendation." />
      <Card>
        <textarea
          rows={10}
          placeholder="Enter JSON payload…"
          value={payload}
          onChange={(e) => setPayload(e.target.value)}
          style={{ width: '100%', fontFamily: 'var(--font-mono)', padding: 8, border: '1px solid var(--border-hairline)', borderRadius: 6, marginBottom: 12 }}
        />
        <Button onClick={handleSubmit} disabled={loading} variant="primary">
          {loading ? 'Scoring…' : 'Score transaction'}
        </Button>
        {error && <p style={{ color: 'var(--risk-block)', marginTop: 8 }}>{error}</p>}
      </Card>

      {result && (
        <Card style={{ marginTop: 20 }}>
          <h3 style={{ margin: 0, fontSize: 16, color: 'var(--text-primary)' }}>Result</h3>
          <StatTile label="Score" value={result.score.toFixed(1)} />
          <TierBadge tier={result.tier} />
          <h4 style={{ marginTop: 12, fontSize: 14, color: 'var(--text-primary)' }}>Top SHAP contributions</h4>
          <ShapBarChart features={result.shap} />
          {result.counterfactual && (
            <div style={{ marginTop: 12 }}>
              <h4 style={{ fontSize: 14, color: 'var(--text-primary)' }}>Counterfactual suggestion</h4>
              <p style={{ color: 'var(--text-secondary)' }}>{result.counterfactual}</p>
            </div>
          )}
        </Card>
      )}
    </div>
  )
}
