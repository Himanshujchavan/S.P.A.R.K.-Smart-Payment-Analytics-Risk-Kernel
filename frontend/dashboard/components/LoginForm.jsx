'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { TextInput, Button } from './Primitives'
import { api } from '../lib/api'
export default function LoginForm() { const router=useRouter(); const [email,setEmail]=useState(''); const [password,setPassword]=useState(''); const [error,setError]=useState(''); const submit=async(e)=>{e.preventDefault();try{const r=await api.login({email,password});localStorage.setItem('spark_access_token',r.access_token);localStorage.setItem('spark_refresh_token',r.refresh_token);router.replace('/')}catch(err){setError(err.message)}}; return <form onSubmit={submit} style={{display:'grid',gap:10}}><TextInput label="Email" type="email" value={email} onChange={e=>setEmail(e.target.value)} required/><TextInput label="Password" type="password" value={password} onChange={e=>setPassword(e.target.value)} required/><Button type="submit">Sign in</Button>{error&&<p style={{color:'var(--risk-block)'}}>{error}</p>}</form> }
