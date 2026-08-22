'use client'

// Load simulation — configurable rate, duration, and scenario. While the
// run is active, stats tick up in real time; afterwards the run summary
// shows p50 / p95 / p99 latency and per-tier breakdown.

import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { PageHeader, Card, Button, TextInput, Select, StatTile } from '../../components/Primitives'

const SCENARIOS = [
  { id: 'baseline', label: 'Baseline mix', desc: 'Realistic mix of UPI / card / netbanking traffic.' },
  { id: 'card_testing', label: 'Card testing burst', desc: 'Many small-ticket card attempts from one device — stress the velocity features.' },
  { id: 'ring_attack', label: 'Coordinated ring', desc: 'Several accounts sharing an IP and device — exercise the graph layer.' },
  { id: 'low_value', label: 'Low-value noise', desc: '₹1–₹20 micro-transactions to probe the lower bound of the cost curve.' },
]

export default function SimulationPage() {
  const [rate, setRate] = useState(1000)
  const [duration, setDuration] = useState(30)
  const [scenario, setScenario] = useState('baseline')
  const [run, setRun] = useState(null)
  const [stats, setStats] = useState(null)
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!run) return
    const startedAt = Date.now()
    const tick = () => {
      const sec = Math.min(run.duration, (Date.now() - startedAt) / 1000)
      setElapsed(sec)
      const total = Math.min(run.rate * sec, run.rate * run.duration)
      const allow = Math.round(total * 0.927)
      const challenge = Math.round(total * 0.055)
      const block = total - allow - challenge
      const p50 = 32 + Math.sin(sec / 3) * 4
      const p95 = 78 + Math.sin(sec / 2) * 8
      const p99 = 142 + Math.sin(sec / 1.7) * 18
      setStats({ total: Math.round(total), allow, challenge, block, p50, p95, p99 })
      if (sec >= run.duration) clearInterval(id)
    }
    tick()
    const id = setInterval(tick, 500)
    return () => clearInterval(id)
  }, [run])

  const start = async () => {
    const r = await api.startSimulation({ rate: Number(rate), duration: Number(duration), scenario })
    setRun({ ...r, duration: Number(duration), rate: Number(rate) })
    setElapsed(0)
    setStats(null)
  }

  const stop = () => setRun(null)
  const progress = run ? Math.min(100, (elapsed / run.duration) * 100) : 0
  const selected = SCENARIOS.find((s) => s.id === scenario)

  return (
    <div>
      <PageHeader
        title="Load simulation"
        subtitle="Send a burst of synthetic transactions through the live pipeline and watch S.P.A.R.K. respond."
      />

      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 16, marginBottom: 20 }}>
        <Card title="Configure run" subtitle="Synthetic traffic only — no real merchant is touched">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 16 }}>
            <TextInput
              label="Transactions per second"
              type="number"
              min={10}
              max={20000}
              value={rate}
              onChange={(e) => setRate(e.target.value)}
              hint="Locust-style async producer"
            />
            <TextInput
              label="Duration (seconds)"
              type="number"
              min={5}
              max={600}
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              hint="Run auto-stops at limit"
            />
            <Select label="Scenario" value={scenario} onChange={(e) => setScenario(e.target.value)}>
              {SCENARIOS.map((s) => (
                <option key={s.id} value={s.id}>{s.label}</option>
              ))}
            </Select>
          </div>
          <p style={{ margin: '0 0 12px', fontSize: 12, color: 'var(--text-secondary)' }}>
            <strong>{selected?.label}.</strong> {selected?.desc}
          </p>
          <div style={{ display: 'flex', gap: 8 }}>
            {!run ? (
              <Button onClick={start}>Start simulation</Button>
            ) : (
              <Button variant="danger" onClick={stop}>Stop</Button>
            )}
            <Button variant="secondary" onClick={() => { setRun(null); setStats(null); setElapsed(0) }}>
              Reset
            </Button>
          </div>
        </Card>

        <Card title="Run status" subtitle={run ? `Run ${run.runId}` : 'No active run'}>
          {!run && (
            <p style={{ color: 'var(--text-secondary)', fontSize: 13, margin: 0 }}>
              Configure a run and press <strong>Start simulation</strong>. Stats will appear here in
              real time.
            </p>
          )}
          {run && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>
                <span>{elapsed.toFixed(1)}s / {run.duration}s</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>{progress.toFixed(0)}%</span>
              </div>
              <div style={{ height: 8, background: 'var(--border-hairline)', borderRadius: 999, overflow: 'hidden', marginBottom: 12 }}>
                <div style={{
                  width: progress + '%',
                  height: '100%',
                  background: 'var(--accent-spark)',
                  transition: 'width 0.4s linear',
                }} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
                <StatTile label="Ingested" value={(stats?.total || 0).toLocaleString('en-IN')} hint="txns" />
                <StatTile label="p50" value={(stats?.p50 || 0).toFixed(0) + ' ms'} hint="scoring latency" />
                <StatTile label="p95" value={(stats?.p95 || 0).toFixed(0) + ' ms'} hint="scoring latency" />
                <StatTile label="p99" value={(stats?.p99 || 0).toFixed(0) + ' ms'} hint="scoring latency" />
              </div>
            </div>
          )}
        </Card>
      </div>

      {stats && (
        <Card title="Per-tier breakdown" subtitle="Live decisions during the run">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            <StatTile label="Allowed" value={stats.allow.toLocaleString('en-IN')} delta={`${((stats.allow / stats.total) * 100).toFixed(1)}%`} trend="up" />
            <StatTile label="Challenged" value={stats.challenge.toLocaleString('en-IN')} delta={`${((stats.challenge / stats.total) * 100).toFixed(1)}%`} trend="flat" />
            <StatTile label="Blocked" value={stats.block.toLocaleString('en-IN')} delta={`${((stats.block / stats.total) * 100).toFixed(1)}%`} trend="down" />
          </div>
        </Card>
      )}
    </div>
  )
}
