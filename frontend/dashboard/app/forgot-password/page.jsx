// Forgot / reset password — recover access to a S.P.A.R.K. account.

import Link from 'next/link'
import { PageHeader, Card, Button, TextInput } from '../../components/Primitives'

export default function ForgotPasswordPage() {
  return (
    <div style={{ maxWidth: 540, margin: '0 auto' }}>
      <PageHeader
        title="Forgot password?"
        subtitle="Enter your email or phone to start the recovery flow."
      />
      <Card>
        <form style={{ display: 'grid', gap: 10 }}>
          <TextInput
            label="Email or phone number"
            name="identifier"
            placeholder="you@merchant.com or +91…"
            required
          />
          <Button type="button">Send reset link</Button>
        </form>
        <p style={{ margin: '12px 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>
          A one-time link will be sent to the address on file. The link expires in 15 minutes.
        </p>
        <div style={{ marginTop: 12, textAlign: 'center', fontSize: 12, color: 'var(--text-secondary)' }}>
          Remembered it? <Link href="/login">Sign in</Link>
        </div>
      </Card>
    </div>
  )
}
