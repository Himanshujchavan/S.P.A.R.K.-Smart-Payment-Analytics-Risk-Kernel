// Login form — used as a smaller embedded component. The full-page
// experience lives in app/login/page.jsx.

import { TextInput, Button } from './Primitives'

export default function LoginForm() {
  return (
    <form style={{ display: 'grid', gap: 10 }}>
      <TextInput label="Email" type="email" name="email" required />
      <TextInput label="Password" type="password" name="password" required />
      <Button type="submit">Sign in</Button>
    </form>
  )
}
