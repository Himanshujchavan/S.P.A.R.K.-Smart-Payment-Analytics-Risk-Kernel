// Cost-curve chart: 3-tier decisioning vs naive binary, plotted across thresholds.

'use client'

import { useEffect, useState } from 'react'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
} from 'recharts'
import { api } from '../lib/api'
import { Card } from './Primitives'

const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })

export default function CostCurveChart() {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getCostCurve().then((d) => {
      setData(d)
      setLoading(false)
    })
  }, [])

  const optimal = data.length
    ? data.reduce((a, b) => (b.threeTier < a.threeTier ? b : a), data[0])
    : null
  const binaryAtOptimal = data.find((d) => d.threshold === optimal?.threshold)

  return (
    <Card
      title="Cost curve — three-tier vs binary"
      subtitle="Estimated ₹ cost across decision thresholds on the held-out test set"
      action={
        optimal && (
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            Optimal @ {optimal.threshold.toFixed(1)} ·{' '}
            <strong style={{ color: 'var(--risk-allow)', fontFamily: 'var(--font-mono)' }}>
              {inr.format(optimal.threeTier)}
            </strong>{' '}
            (binary: {inr.format(binaryAtOptimal?.binary || 0)})
          </span>
        )
      }
    >
      <div style={{ width: '100%', height: 280 }}>
        {loading ? (
          <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>Computing cost curve…</p>
        ) : (
          <ResponsiveContainer>
            <LineChart data={data} margin={{ top: 10, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--border-hairline)" strokeDasharray="3 3" />
              <XAxis
                dataKey="threshold"
                tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                label={{ value: 'Block threshold (%)', position: 'insideBottom', offset: -2, fill: 'var(--text-secondary)', fontSize: 11 }}
                tickFormatter={(v) => v.toFixed(0)}
              />
              <YAxis
                tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                tickFormatter={(v) => '₹' + (v / 1000).toFixed(0) + 'k'}
                width={60}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--bg-surface-raised)',
                  border: '1px solid var(--border-hairline)',
                  borderRadius: 6,
                  fontSize: 12,
                }}
                formatter={(v) => inr.format(v)}
                labelFormatter={(l) => `Threshold ${l.toFixed(1)}%`}
              />
              <Legend wrapperStyle={{ fontSize: 12, color: 'var(--text-secondary)' }} />
              {optimal && (
                <ReferenceLine
                  x={optimal.threshold}
                  stroke="var(--accent-spark)"
                  strokeDasharray="4 4"
                  label={{ value: 'Optimal', fill: 'var(--accent-spark)', fontSize: 10, position: 'top' }}
                />
              )}
              <Line
                type="monotone"
                dataKey="threeTier"
                name="Three-tier (S.P.A.R.K.)"
                stroke="var(--accent-spark)"
                strokeWidth={2.5}
                dot={false}
                isAnimationActive
                animationDuration={700}
              />
              <Line
                type="monotone"
                dataKey="binary"
                name="Binary block/allow"
                stroke="var(--text-secondary)"
                strokeWidth={1.5}
                strokeDasharray="6 4"
                dot={false}
                isAnimationActive
                animationDuration={700}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
      <p style={{ margin: 0, fontSize: 11, color: 'var(--text-secondary)' }}>
        S.P.A.R.K.'s three-tier decisioning recovers{' '}
        <strong style={{ color: 'var(--risk-allow)' }}>
          {inr.format((binaryAtOptimal?.binary || 0) - (optimal?.threeTier || 0))}
        </strong>{' '}
        per held-out test set vs. a binary baseline by routing medium-risk transactions to step-up
        verification instead of blocking good customers outright.
      </p>
    </Card>
  )
}
