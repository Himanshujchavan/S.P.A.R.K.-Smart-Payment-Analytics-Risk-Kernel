// Top navigation — groups S.P.A.R.K. by task flow (Monitor / Investigate / Operate / Account).
// Uses Next.js <Link> for client-side navigation, and exposes the theme toggle.

'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useContext } from 'react'
import { ThemeContext } from './ThemeProvider'

const PRIMARY = [
  { href: '/', label: 'Dashboard' },
  { href: '/transactions', label: 'Transactions' },
  { href: '/metrics', label: 'Metrics' },
  { href: '/rings', label: 'Rings' },
]

const INVESTIGATE = [
  { href: '/audit', label: 'Audit trail' },
  { href: '/model-health', label: 'Model health' },
]

const OPERATE = [
  { href: '/simulation', label: 'Simulation' },
  { href: '/settings', label: 'Settings' },
]

function NavGroup({ items, pathname, onNavigate }) {
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
      {items.map((item) => {
        const active = item.href === '/' ? pathname === '/' : pathname?.startsWith(item.href)
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            style={{
              padding: '6px 10px',
              borderRadius: 6,
              fontSize: 13,
              fontWeight: 500,
              color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
              background: active ? 'var(--bg-surface)' : 'transparent',
              textDecoration: 'none',
              transition: 'background var(--hover-duration) var(--page-trans-ease), color var(--hover-duration) var(--page-trans-ease)',
            }}
          >
            {item.label}
          </Link>
        )
      })}
    </div>
  )
}

export default function Navbar() {
  const pathname = usePathname()
  const { theme, setTheme } = useContext(ThemeContext) || { theme: 'light', setTheme: () => {} }
  const cycleTheme = () => setTheme(theme === 'light' ? 'dark' : theme === 'dark' ? 'system' : 'light')

  return (
    <header
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 50,
        background: 'var(--bg-base)',
        borderBottom: '1px solid var(--border-hairline)',
        backdropFilter: 'saturate(180%) blur(6px)',
      }}
    >
      <div
        style={{
          maxWidth: 1400,
          margin: '0 auto',
          padding: '10px 20px',
          display: 'flex',
          alignItems: 'center',
          gap: 16,
        }}
      >
        <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
          <span
            style={{
              width: 26,
              height: 26,
              borderRadius: 6,
              background: 'linear-gradient(135deg, var(--navy-primary), var(--accent-spark))',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              fontWeight: 700,
              fontSize: 12,
              fontFamily: 'var(--font-mono)',
            }}
          >
            S
          </span>
          <span style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.1 }}>
            <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, color: 'var(--text-primary)', fontSize: 14 }}>
              S.P.A.R.K.
            </span>
            <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Smart Payment Analytics & Risk Kernel</span>
          </span>
        </Link>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <NavGroup items={PRIMARY} pathname={pathname} />
          <span style={{ color: 'var(--border-hairline)' }}>|</span>
          <NavGroup items={INVESTIGATE} pathname={pathname} />
          <span style={{ color: 'var(--border-hairline)' }}>|</span>
          <NavGroup items={OPERATE} pathname={pathname} />
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            onClick={cycleTheme}
            aria-label="Toggle theme"
            style={{
              padding: '6px 10px',
              borderRadius: 6,
              border: '1px solid var(--border-hairline)',
              background: 'var(--bg-surface)',
              color: 'var(--text-secondary)',
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            {theme === 'light' ? '☀' : theme === 'dark' ? '☾' : '◐'} {theme}
          </button>
          <Link
            href="/profile"
            style={{
              width: 30,
              height: 30,
              borderRadius: 999,
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-hairline)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-primary)',
              fontSize: 12,
              fontWeight: 600,
              textDecoration: 'none',
            }}
            aria-label="Profile"
          >
            HC
          </Link>
        </div>
      </div>
    </header>
  )
}
