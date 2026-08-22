// Signup page — create a S.P.A.R.K. account and connect to Razorpay.

import Link from 'next/link'
import { PageHeader, Card, Button, TextInput, Select } from '../../components/Primitives'

export default function SignupPage() {
  return (
    <div style={{ maxWidth: 760, margin: '0 auto' }}>
      <PageHeader
        title="Create your S.P.A.R.K. account"
        subtitle="Set up risk monitoring for your Razorpay merchant account in a few minutes."
      />
      <Card title="Account details" subtitle="You can invite teammates after the account is created">
        <form style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
          <TextInput label="Full name" name="name" required />
          <TextInput label="Work email" name="email" type="email" required />
          <TextInput label="Password" name="password" type="password" hint="At least 8 characters, one number" required />
          <TextInput label="Phone (for SMS alerts)" name="phone" type="tel" />
          <TextInput label="Organization / merchant name" name="org" required />
          <TextInput label="Razorpay merchant ID" name="merchant_id" placeholder="e.g. Hc1aB2c3D4e5F6" />
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
          <div style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-secondary)' }}>
              <input type="checkbox" required /> I agree to the Terms of Service and Privacy Policy
            </label>
            <Button type="button">Create account</Button>
          </div>
        </form>
        <div style={{ margin: '14px 0', color: 'var(--text-secondary)', fontSize: 11, textAlign: 'center' }}>OR SIGN UP WITH</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button variant="secondary" style={{ flex: 1 }}>Google</Button>
          <Button variant="secondary" style={{ flex: 1 }}>Phone</Button>
        </div>
        <div style={{ marginTop: 12, textAlign: 'center', fontSize: 12, color: 'var(--text-secondary)' }}>
          Already have an account? <Link href="/login">Sign in</Link>
        </div>
      </Card>
    </div>
  )
}
