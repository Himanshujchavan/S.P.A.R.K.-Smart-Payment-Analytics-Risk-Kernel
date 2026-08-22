'use client'

// Profile — account details, API key, and recent sign-in history.

import { useState } from 'react'
import { PageHeader, Card, Button, TextInput, Select } from '../../components/Primitives'

export default function ProfilePage() {
  const [saved, setSaved] = useState(false)
  const save = () => { setSaved(true); setTimeout(() => setSaved(false), 1800) }

  return (
    <div>
      <PageHeader
        title="Profile"
        subtitle="Your account details and sign-in activity."
        actions={saved ? <span style={{ fontSize: 12, color: 'var(--risk-allow)' }}>✓ Saved</span> : <Button onClick={save}>Save changes</Button>}
      />

      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 16 }}>
        <Card title="Account" subtitle="Used across the S.P.A.R.K. dashboard and Razorpay Risk API">
          <form
            onSubmit={(e) => { e.preventDefault(); save() }}
            style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}
          >
            <TextInput label="Full name" defaultValue="Himanshu Chavan" />
            <TextInput label="Email" type="email" defaultValue="himanshu@spark-merchant.example" />
            <TextInput label="Phone" defaultValue="+91 98200 12345" />
            <TextInput label="Organization" defaultValue="SPARK Demo Merchant" />
            <Select label="Role" defaultValue="Risk Analyst">
              <option>Merchant Owner</option>
              <option>Risk Analyst</option>
              <option>Finance</option>
              <option>Engineering</option>
              <option>Other</option>
            </Select>
            <Select label="Time zone" defaultValue="Asia/Kolkata">
              <option>Asia/Kolkata (UTC+5:30)</option>
              <option>UTC</option>
              <option>America/New_York</option>
              <option>Europe/London</option>
            </Select>
          </form>
        </Card>

        <Card title="API key" subtitle="Read-only access to S.P.A.R.K. endpoints">
          <code style={{
            display: 'block',
            padding: 10,
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-hairline)',
            borderRadius: 6,
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            color: 'var(--text-primary)',
            wordBreak: 'break-all',
          }}>
            rk_live_8a4f29c7e3b1d6f5a0c9e8b7d4f2a1c6
          </code>
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <Button variant="secondary" onClick={() => navigator.clipboard?.writeText('rk_live_8a4f29c7e3b1d6f5a0c9e8b7d4f2a1c6')}>
              Copy
            </Button>
            <Button variant="secondary">Rotate key</Button>
          </div>
        </Card>
      </div>

      <div style={{ height: 16 }} />

      <Card title="Recent sign-ins" subtitle="Last 5 sign-in events for this account">
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[
            { when: '2026-08-22 09:18 IST', ip: '10.42.18.7', city: 'Pune, IN', device: 'Chrome on macOS' },
            { when: '2026-08-21 17:42 IST', ip: '10.42.18.7', city: 'Pune, IN', device: 'Chrome on macOS' },
            { when: '2026-08-20 22:11 IST', ip: '49.36.112.4', city: 'Mumbai, IN', device: 'Safari on iPhone' },
            { when: '2026-08-19 11:03 IST', ip: '10.42.18.7', city: 'Pune, IN', device: 'Chrome on macOS' },
            { when: '2026-08-18 08:51 IST', ip: '10.42.18.7', city: 'Pune, IN', device: 'Chrome on macOS' },
          ].map((s, i) => (
            <li key={i} style={{
              display: 'grid',
              gridTemplateColumns: '160px 1fr 1fr 1fr',
              gap: 12,
              padding: 10,
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-hairline)',
              borderRadius: 6,
              fontSize: 12,
            }}>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{s.when}</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{s.ip}</span>
              <span style={{ color: 'var(--text-secondary)' }}>{s.city}</span>
              <span style={{ color: 'var(--text-secondary)' }}>{s.device}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
