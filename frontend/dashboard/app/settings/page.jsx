'use client'

// Settings — appearance, decision thresholds, notifications, integrations.

import { useContext, useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { ThemeContext } from '../../components/ThemeProvider'
import { PageHeader, Card, Button, TextInput, Select } from '../../components/Primitives'

export default function SettingsPage() {
  const { theme, setTheme } = useContext(ThemeContext) || { theme: 'light', setTheme: () => {} }
  const [allow, setAllow] = useState(45)
  const [block, setBlock] = useState(75)
  const [error, setError] = useState('')
  useEffect(() => { api.getModelHealth().then(h => { setAllow(Math.round((h.model.thresholds.allow ?? 0.45)*100)); setBlock(Math.round((h.model.thresholds.challenge ?? 0.75)*100)) }).catch(e => setError(e.message)) }, [])
  const [ring, setRing] = useState(true)
  const [drift, setDrift] = useState(true)
  const [saved, setSaved] = useState(false)

  const save = async () => { if (allow >= block) { setError('Allow threshold must be below block threshold'); return } setError(''); try { await api.updateThresholds({allow: allow/100, challenge: block/100}); setSaved(true); setTimeout(() => setSaved(false), 1800) } catch (e) { setError(e.message) } }

  return (
    <div>
      <PageHeader
        title="Settings"
        subtitle="Calibrate thresholds, manage integrations, and tailor notifications."
      />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
        <Card title="Appearance" subtitle="Theme applies across the dashboard">
          <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
            {['light', 'dark', 'system'].map((t) => (
              <button
                key={t}
                onClick={() => setTheme(t)}
                style={{
                  flex: 1,
                  padding: '10px',
                  borderRadius: 6,
                  border: '1px solid ' + (theme === t ? 'var(--accent-spark)' : 'var(--border-hairline)'),
                  background: theme === t ? 'color-mix(in srgb, var(--accent-spark) 10%, transparent)' : 'var(--bg-surface)',
                  color: 'var(--text-primary)',
                  cursor: 'pointer',
                  textTransform: 'capitalize',
                  fontWeight: theme === t ? 600 : 500,
                }}
              >
                {t === 'light' ? '☀ Light' : t === 'dark' ? '☾ Dark' : '◐ System'}
              </button>
            ))}
          </div>
          <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)' }}>
            "System" follows your OS preference and switches automatically.
          </p>
        </Card>

        <Card title="Integrations" subtitle="External keys and webhook destinations">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <TextInput label="Razorpay key id" defaultValue="rzp_test_Hc1aB2c3D4e5" />
            <TextInput
              label="Read-only API key"
              value="Not configured"
              readOnly
              hint="No secret is exposed in the dashboard. Configure secrets through the deployment environment."
            />
            <TextInput label="Slack alert webhook" defaultValue="https://hooks.slack.com/services/T0•••/B0•••/•••" />
          </div>
        </Card>
      </div>

      <Card
        title="Decision thresholds"
        subtitle="Calibrated to minimize total cost across false positives and missed fraud. Adjust with care — every change is logged."
        action={saved ? <span style={{ fontSize: 12, color: 'var(--risk-allow)' }}>✓ Saved</span> : <Button onClick={save}>Save thresholds</Button>}
      >
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          <TextInput
            label="Allow below"
            type="number"
            min={0}
            max={100}
            value={allow}
            onChange={(e) => setAllow(Number(e.target.value))}
            hint={`Score 0–100, current ${(allow / 100).toFixed(2)}`}
          />
          <TextInput
            label="Challenge between"
            type="number"
            readOnly
            value={`${allow} – ${block}`}
            hint="Read-only — derived from the two above"
          />
          <TextInput
            label="Block above"
            type="number"
            min={0}
            max={100}
            value={block}
            onChange={(e) => setBlock(Number(e.target.value))}
            hint={`Score 0–100, current ${(block / 100).toFixed(2)}`}
          />
        </div>
        <p style={{ margin: '12px 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>
          These thresholds are tuned on the held-out test set using a cost-sensitive optimization
          (1 missed fraud ≈ 8 wrongly-blocked legitimate orders). Changing them will shift the
          precision/recall trade-off — see the <a href="/metrics">metrics page</a> after saving.
        </p>
      </Card>{error && <p style={{color:'var(--risk-block)',fontSize:12}}>{error}</p>}

      <div style={{ height: 16 }} />
      <Card title="Notifications" subtitle="When should S.P.A.R.K. ping you?">
        <label style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 8, borderRadius: 6, cursor: 'pointer' }}>
          <input type="checkbox" checked={ring} onChange={(e) => setRing(e.target.checked)} />
          <div>
            <div style={{ fontSize: 13, color: 'var(--text-primary)' }}>Email me when a new abuse ring is detected</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Routed to security@your-merchant.example</div>
          </div>
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 8, borderRadius: 6, cursor: 'pointer' }}>
          <input type="checkbox" checked={drift} onChange={(e) => setDrift(e.target.checked)} />
          <div>
            <div style={{ fontSize: 13, color: 'var(--text-primary)' }}>Email me when model drift is flagged (PSI &gt; 0.1)</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Suggests the model should be retrained.</div>
          </div>
        </label>
      </Card>
    </div>
  )
}
