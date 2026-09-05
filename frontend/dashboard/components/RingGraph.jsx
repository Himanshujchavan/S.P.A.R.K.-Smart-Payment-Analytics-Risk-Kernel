// Lightweight abuse-ring visualization: members of a ring laid out on a
// circle with shared-attribute edges. Pure SVG, no external graph lib
// (the production version swaps in NetworkX/d3-force data).

export default function RingGraph({ ring, width = 360, height = 240 }) {
  if (!ring) return null
  const members = ring.accountIds.slice(0, 14)
  const cx = width / 2
  const cy = height / 2
  const r = Math.min(width, height) / 2 - 24

  // center node representing the shared attribute
  if (!members.length) return <div style={{padding:20,color:'var(--text-secondary)'}}>No member accounts are available for this ring.</div>

  const nodes = members.map((id, i) => {
    const angle = (i / members.length) * Math.PI * 2 - Math.PI / 2
    return {
      id,
      x: cx + Math.cos(angle) * r,
      y: cy + Math.sin(angle) * r,
    }
  })

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
      <defs>
        <radialGradient id="ring-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="var(--risk-block)" stopOpacity="0.18" />
          <stop offset="100%" stopColor="var(--risk-block)" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx={cx} cy={cy} r={r + 12} fill="url(#ring-glow)" />
      {nodes.map((n) => (
        <line
          key={'e' + n.id}
          x1={cx}
          y1={cy}
          x2={n.x}
          y2={n.y}
          stroke="var(--risk-block)"
          strokeOpacity="0.35"
          strokeWidth="1"
        />
      ))}
      {nodes.map((n, i) => {
        // connect adjacent ring members to suggest a cluster
        const next = nodes[(i + 1) % nodes.length]
        return (
          <line
            key={'p' + n.id}
            x1={n.x}
            y1={n.y}
            x2={next.x}
            y2={next.y}
            stroke="var(--risk-block)"
            strokeOpacity="0.18"
            strokeWidth="1"
          />
        )
      })}
      <circle cx={cx} cy={cy} r="22" fill="var(--bg-surface-raised)" stroke="var(--risk-block)" strokeWidth="1.5" />
      <text
        x={cx}
        y={cy - 2}
        textAnchor="middle"
        fontSize="9"
        fill="var(--text-secondary)"
        style={{ textTransform: 'uppercase', letterSpacing: 0.5 }}
      >
        Shared
      </text>
      <text x={cx} y={cy + 10} textAnchor="middle" fontSize="10" fill="var(--text-primary)" fontWeight="600">
        {ring.sharedAttribute.replace(/_/g, ' ')}
      </text>
      {nodes.map((n, i) => (
        <g key={n.id}>
          <circle cx={n.x} cy={n.y} r="9" fill="var(--bg-surface-raised)" stroke="var(--risk-block)" strokeWidth="1.2" />
          <text x={n.x} y={n.y + 3} textAnchor="middle" fontSize="9" fill="var(--text-primary)" fontFamily="var(--font-mono)">
            {String(i + 1)}
          </text>
        </g>
      ))}
    </svg>
  )
}
