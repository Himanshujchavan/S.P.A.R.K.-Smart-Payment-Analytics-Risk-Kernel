// Login page — branded for S.P.A.R.K., with Google / phone SSO options.

import Link from 'next/link'
import { PageHeader, Card, Button, TextInput } from '../../components/Primitives'

export default function LoginPage() {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1.2fr 1fr',
        gap: 24,
        alignItems: 'stretch',
        maxWidth: 1100,
        margin: '0 auto',
      }}
    >
      <div
        style={{
          padding: 32,
          borderRadius: 12,
          background: 'linear-gradient(135deg, var(--navy-primary), var(--navy-mid))',
          color: '#fff',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: 1, opacity: 0.7 }}>S.P.A.R.K.</span>
        <h1
          style={{
            margin: 0,
            fontSize: 30,
            fontFamily: 'var(--font-display)',
            fontWeight: 600,
            lineHeight: 1.15,
          }}
        >
          Catch the fraud your<br />binary rule engine misses.
        </h1>
        <p style={{ margin: 0, opacity: 0.85, fontSize: 14, lineHeight: 1.5, maxWidth: 460 }}>
          Real-time three-tier risk decisioning for Razorpay. Score every transaction, surface
          coordinated abuse rings, and explain every block with a counterfactual.
        </p>
        <ul style={{ listStyle: 'none', padding: 0, margin: '8px 0 0', display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
          <li>· Allow / Challenge / Block — not a binary cutoff</li>
          <li>· Graph layer catches coordinated rings</li>
          <li>· Self-monitors drift, every decision audited</li>
        </ul>
      </div>

      <Card title="Sign in to S.P.A.R.K." subtitle="Monitor risk across your Razorpay transactions in real time.">
        <form action="/dashboard" method="GET" style={{ display: 'grid', gap: 10 }}>
          <TextInput label="Email" name="email" type="email" placeholder="you@merchant.com" required />
          <TextInput label="Password" name="password" type="password" placeholder="••••••••" required />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12 }}>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--text-secondary)' }}>
              <input type="checkbox" /> Keep me signed in
            </label>
            <Link href="/forgot-password" style={{ fontSize: 12 }}>Forgot password?</Link>
          </div>
          <Button type="submit">Sign in</Button>
        </form>
        <div style={{ margin: '14px 0', color: 'var(--text-secondary)', fontSize: 11, textAlign: 'center' }}>OR CONTINUE WITH</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button variant="secondary" style={{ flex: 1 }}>Google</Button>
          <Button variant="secondary" style={{ flex: 1 }}>Phone</Button>
        </div>
        <div style={{ marginTop: 12, textAlign: 'center', fontSize: 12, color: 'var(--text-secondary)' }}>
          Don't have an account? <Link href="/signup">Create one</Link>
        </div>
        <p style={{ margin: '12px 0 0', fontSize: 11, color: 'var(--text-secondary)', textAlign: 'center' }}>
          Protected by S.P.A.R.K. — every sign-in is logged for your account's security.
        </p>
      </Card>
    </div>
  )
}
