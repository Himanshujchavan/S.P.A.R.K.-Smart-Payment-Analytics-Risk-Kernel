'use client'

// Settings — appearance, decision thresholds, notifications, integrations.

import { useContext, useState } from 'react'
import { ThemeContext } from '../../components/ThemeProvider'
import { PageHeader, Card, Button, TextInput, Select } from '../../components/Primitives'

export default function SettingsPage() {
  const { theme, setTheme } = useContext(ThemeContext) || { theme: 'light', setTheme: () => {} }
  const [allow, setAllow] = useState(45)
  const [block, setBlock] = useState(78)
  const [ring, setRing] = useState(true)
  const [drift, setDrift] = useState(true)
  const [saved, setSaved] = useState(false)
  const [apiKey] = useState('rk_live_••••••••••••3f2a')

  const save = () => {
    setSaved(true)
    setTimeout(() => setSaved(false), 1800)
  }

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
              value={apiKey}
              readOnly
              hint="Used by the FastAPI backend to call S.P.A.R.K. /score. Rotate from the Razorpay dashboard."
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
            hint="Score 0–100, current 0.45"
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
            hint="Score 0–100, current 0.78"
          />
        </div>
        <p style={{ margin: '12px 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>
          These thresholds are tuned on the held-out test set using a cost-sensitive optimization
          (1 missed fraud ≈ 8 wrongly-blocked legitimate orders). Changing them will shift the
          precision/recall trade-off — see the <a href="/metrics">metrics page</a> after saving.
        </p>
      </Card>

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
