// Signup page — create a S.P.A.R.K. account and connect to Razorpay.

'use client'

import Link from 'next/link'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '../../lib/api'
import { PageHeader, Card, Button, TextInput, Select } from '../../components/Primitives'

export default function SignupPage() {
  const router = useRouter(); const [form,setForm]=useState({name:'',email:'',password:'',phone:'',org:''}); const [error,setError]=useState(''); const [loading,setLoading]=useState(false)
  const update=(e)=>setForm({...form,[e.target.name]:e.target.value})
  const submit=async(e)=>{
    e.preventDefault();
    setError('');
    const password = form.password;
    if (password.length < 8 || !/\d/.test(password) || !/[A-Z]/.test(password)) {
      setError('Password must be at least 8 characters and include one uppercase letter and one number.');
      return;
    }
    setLoading(true);
    try {
      const r = await api.signup({
        full_name: form.name.trim(),
        email: form.email.trim() || null,
        password,
        phone: form.phone.trim() || null,
        merchant_name: form.org.trim() || null,
      });
      localStorage.setItem('spark_access_token', r.access_token);
      document.cookie = `spark_access_token=${r.access_token}; Path=/; SameSite=Lax`;
      localStorage.setItem('spark_refresh_token', r.refresh_token);
      router.replace('/');
      router.refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 760, margin: '0 auto' }}>
      <PageHeader
        title="Create your S.P.A.R.K. account"
        subtitle="Set up risk monitoring for your Razorpay merchant account in a few minutes."
      />
      <Card title="Account details" subtitle="You can invite teammates after the account is created">
        <form onSubmit={submit} style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
          <TextInput label="Full name" name="name" value={form.name} onChange={update} required />
          <TextInput label="Work email" name="email" type="email" value={form.email} onChange={update} required />
          <TextInput label="Password" name="password" type="password" value={form.password} onChange={update} hint="At least 8 characters, one uppercase letter, and one number" required />
          <TextInput label="Phone (for SMS alerts)" name="phone" type="tel" value={form.phone} onChange={update} />
          <TextInput label="Organization / merchant name" name="org" value={form.org} onChange={update} required />
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
            <Button type="submit" disabled={loading}>{loading ? 'Creating…' : 'Create account'}</Button>
          </div>
        </form>{error && <p style={{color:'var(--risk-block)'}}>{error}</p>}
        <div style={{ margin: '14px 0', color: 'var(--text-secondary)', fontSize: 11, textAlign: 'center' }}>OR SIGN UP WITH</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button variant="secondary" style={{ flex: 1 }} disabled>Google (not configured)</Button>
          <Button variant="secondary" style={{ flex: 1 }} disabled>Phone (not configured)</Button>
        </div>
        <div style={{ marginTop: 12, textAlign: 'center', fontSize: 12, color: 'var(--text-secondary)' }}>
          Already have an account? <Link href="/login">Sign in</Link>
        </div>
      </Card>
    </div>
  )
}
