// Signup form — used as a smaller embedded component. The full-page
// experience lives in app/signup/page.jsx.

import { TextInput, Select, Button } from './Primitives'

export default function SignupForm() {
  return (
    <form style={{ display: 'grid', gap: 10 }}>
      <TextInput label="Full name" name="name" required />
      <TextInput label="Work email" type="email" name="email" required />
      <TextInput label="Password" type="password" name="password" required />
      <TextInput label="Organization" name="org" required />
      <Select label="Role" defaultValue="Risk Analyst">
        <option>Merchant Owner</option>
        <option>Risk Analyst</option>
        <option>Finance</option>
        <option>Engineering</option>
        <option>Other</option>
      </Select>
      <Button type="submit">Create account</Button>
    </form>
  )
}
