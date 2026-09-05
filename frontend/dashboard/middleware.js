import { NextResponse } from 'next/server'
export function middleware(request) {
  const path=request.nextUrl.pathname
  if (path.startsWith('/login') || path.startsWith('/signup') || path.startsWith('/forgot-password') || path.startsWith('/_next') || path.includes('.')) return NextResponse.next()
  const token=request.cookies.get('spark_access_token')?.value
  if (!token) return NextResponse.redirect(new URL('/login', request.url))
  return NextResponse.next()
}
export const config={matcher:['/((?!api).*)']}
