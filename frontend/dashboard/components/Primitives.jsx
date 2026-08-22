// Shared visual primitives for the dashboard — keeps every page aligned
// to the same design tokens (colors, spacing, radii) defined in styles/tokens.css.

import { TIER_META } from '../lib/types'

export function Card({ title, subtitle, action, children, style }) {
  return (
    <section
      className="card surface-raised"
      style={{
        padding: 16,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        ...style,
      }}
    >
      {(title || action) && (
        <header style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
          <div>
            {title && (
              <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                {title}
              </h3>
            )}
            {subtitle && (
              <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>{subtitle}</p>
            )}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  )
}

export function StatTile({ label, value, delta, trend, hint }) {
  const trendColor =
    trend === 'up' ? 'var(--risk-allow)' : trend === 'down' ? 'var(--risk-block)' : 'var(--text-secondary)'
  return (
    <div
      className="card surface-raised"
      style={{ padding: 14, minWidth: 180, flex: '1 1 180px', display: 'flex', flexDirection: 'column', gap: 6 }}
    >
      <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.4, color: 'var(--text-secondary)' }}>
        {label}
      </div>
      <div
        style={{
          fontSize: 22,
          fontFamily: 'var(--font-mono)',
          color: 'var(--text-primary)',
          fontWeight: 500,
        }}
      >
        {value}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        {delta != null && (
          <span style={{ fontSize: 12, color: trendColor, fontFamily: 'var(--font-mono)' }}>{delta}</span>
        )}
        {hint && <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{hint}</span>}
      </div>
    </div>
  )
}

export function TierBadge({ tier, withDot = true }) {
  const normalizedKey = typeof tier === 'string' ? tier.toLowerCase().replace(/ed$/, '') : ''
  const meta = TIER_META[normalizedKey] || TIER_META[tier] || {
    label: typeof tier === 'string' ? tier.charAt(0).toUpperCase() + tier.slice(1) : 'Unknown',
    color: 'var(--text-secondary)',
  }
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '2px 8px',
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: 0.2,
        color: meta.color,
        background: 'color-mix(in srgb, ' + meta.color + ' 12%, transparent)',
        border: '1px solid color-mix(in srgb, ' + meta.color + ' 35%, transparent)',
        transition: 'transform var(--badge-scale-duration) var(--page-trans-ease)',
      }}
    >
      {withDot && (
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: 999,
            background: meta.color,
            display: 'inline-block',
          }}
        />
      )}
      {meta.label}
    </span>
  )
}

export function ScoreBar({ value }) {
  const pct = Math.max(0, Math.min(100, value))
  const color = pct >= 78 ? 'var(--risk-block)' : pct >= 45 ? 'var(--risk-challenge)' : 'var(--risk-allow)'
  return (
    <div
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      style={{
        position: 'relative',
        height: 6,
        width: '100%',
        background: 'var(--border-hairline)',
        borderRadius: 999,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          width: pct + '%',
          height: '100%',
          background: color,
          transition: 'width var(--counter-duration) var(--page-trans-ease)',
        }}
      />
    </div>
  )
}

export function Button({ children, variant = 'primary', ...rest }) {
  const styles = {
    primary: { background: 'var(--accent-spark)', color: '#fff', border: '1px solid var(--accent-spark)' },
    secondary: { background: 'var(--bg-surface)', color: 'var(--text-primary)', border: '1px solid var(--border-hairline)' },
    ghost: { background: 'transparent', color: 'var(--text-primary)', border: '1px solid transparent' },
    danger: { background: 'var(--risk-block)', color: '#fff', border: '1px solid var(--risk-block)' },
  }
  return (
    <button
      {...rest}
      style={{
        ...styles[variant],
        padding: '8px 12px',
        borderRadius: 6,
        fontSize: 13,
        fontWeight: 600,
        cursor: 'pointer',
        transition: 'background var(--hover-duration) var(--page-trans-ease)',
        ...rest.style,
      }}
    >
      {children}
    </button>
  )
}

export function TextInput({ label, hint, ...rest }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {label && (
        <span style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.3 }}>
          {label}
        </span>
      )}
      <input
        {...rest}
        style={{
          padding: '8px 10px',
          borderRadius: 6,
          border: '1px solid var(--border-hairline)',
          background: 'var(--bg-surface-raised)',
          color: 'var(--text-primary)',
          fontSize: 13,
          fontFamily: 'var(--font-sans)',
          ...rest.style,
        }}
      />
      {hint && <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{hint}</span>}
    </label>
  )
}

export function Select({ label, children, ...rest }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {label && (
        <span style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.3 }}>
          {label}
        </span>
      )}
      <select
        {...rest}
        style={{
          padding: '8px 10px',
          borderRadius: 6,
          border: '1px solid var(--border-hairline)',
          background: 'var(--bg-surface-raised)',
          color: 'var(--text-primary)',
          fontSize: 13,
          fontFamily: 'var(--font-sans)',
          ...rest.style,
        }}
      >
        {children}
      </select>
    </label>
  )
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 16, marginBottom: 18 }}>
      <div>
        <h1
          style={{
            margin: 0,
            fontSize: 22,
            fontFamily: 'var(--font-display)',
            fontWeight: 600,
            color: 'var(--text-primary)',
          }}
        >
          {title}
        </h1>
        {subtitle && (
          <p style={{ margin: '4px 0 0', color: 'var(--text-secondary)', fontSize: 13, maxWidth: 720 }}>{subtitle}</p>
        )}
      </div>
      {actions && <div style={{ display: 'flex', gap: 8 }}>{actions}</div>}
    </header>
  )
}

export function DataTable({ columns, rows, empty = 'No records to show', getRowHref }) {
  return (
    <div
      className="card"
      style={{ padding: 0, overflow: 'hidden', borderRadius: 8 }}
    >
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: 'var(--bg-surface)' }}>
              {columns.map((c) => (
                <th
                  key={c.key}
                  style={{
                    textAlign: c.align || 'left',
                    padding: '10px 12px',
                    fontSize: 11,
                    textTransform: 'uppercase',
                    letterSpacing: 0.4,
                    color: 'var(--text-secondary)',
                    borderBottom: '1px solid var(--border-hairline)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} style={{ padding: 24, textAlign: 'center', color: 'var(--text-secondary)' }}>
                  {empty}
                </td>
              </tr>
            ) : (
              rows.map((row, i) => (
                <tr
                  key={row.id || i}
                  className="spark-data-row"
                  style={{
                    borderBottom: '1px solid var(--border-hairline)',
                    cursor: getRowHref ? 'pointer' : 'default',
                    transition: 'background var(--hover-duration) var(--page-trans-ease)',
                  }}
                >
                  {columns.map((c) => (
                    <td
                      key={c.key}
                      style={{
                        padding: '10px 12px',
                        textAlign: c.align || 'left',
                        color: 'var(--text-primary)',
                        whiteSpace: c.nowrap ? 'nowrap' : 'normal',
                        fontFamily: c.mono ? 'var(--font-mono)' : 'var(--font-sans)',
                      }}
                    >
                      {c.render ? c.render(row) : row[c.key]}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
