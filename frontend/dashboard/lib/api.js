// Centralized API client + seed data for the S.P.A.R.K. dashboard.
// In production these functions would call the FastAPI backend; here we
// keep a deterministic in-memory mock so the UI renders with realistic
// content even before the API is wired up. Each function returns a
// Promise to keep the call sites future-compatible with real fetches.
//
// Types live in lib/types.js (JSDoc typedefs) — we don't import them
// here since plain JS doesn't need runtime type imports.

const now = () => new Date()
const isoMinusMinutes = (m) => new Date(Date.now() - m * 60_000).toISOString()
const isoMinusDays = (d) => new Date(Date.now() - d * 86_400_000).toISOString()

const CITIES = ['Bengaluru', 'Mumbai', 'Delhi', 'Hyderabad', 'Pune', 'Chennai', 'Kolkata', 'Ahmedabad']
const METHODS = /** @type {const} */ (['upi', 'card', 'netbanking', 'wallet', 'emandate'])
const FIRST = ['Aarav', 'Diya', 'Vihaan', 'Anaya', 'Reyansh', 'Saanvi', 'Ayaan', 'Myra', 'Krishna', 'Ishaan']
const LAST = ['Sharma', 'Verma', 'Patel', 'Iyer', 'Khan', 'Reddy', 'Nair', 'Das', 'Mehta', 'Joshi']

function pick(arr, i) { return arr[i % arr.length] }
function pad(n) { return String(n).padStart(2, '0') }

// Deterministic pseudo-random so the dashboard renders consistently.
function rand(seed) {
  let s = seed | 0
  return () => {
    s = (s * 1664525 + 1013904223) | 0
    return ((s >>> 0) % 10000) / 10000
  }
}

const r = rand(42)

function makeTransactions(count = 60) {
  /** @type {import('./types').Transaction[]} */
  const out = []
  for (let i = 0; i < count; i++) {
    const score = Math.floor(r() * 1000) / 10
    const tier = score >= 78 ? 'block' : score >= 45 ? 'challenge' : 'allow'
    const amount = Math.round(150 + r() * 9850)
    const userId = `usr_${pad((i * 7) % 999)}`
    const ringId = i % 11 === 0 ? `ring_${(i % 4) + 1}` : undefined
    out.push({
      id: `txn_${(Date.now() - i * 41_000).toString(36)}`,
      userId,
      userName: `${pick(FIRST, i + 3)} ${pick(LAST, i + 5)}`,
      merchantId: 'merch_001',
      amount,
      currency: 'INR',
      method: pick(METHODS, i + 1),
      cardBin: `4${pad(((i * 13) % 9999))}`.slice(0, 6),
      deviceFingerprint: `dev_${(i * 3 + 7) % 200}`,
      ipAddress: `10.${(i * 5) % 250}.${(i * 11) % 250}.${(i * 17) % 250}`,
      city: pick(CITIES, i + 2),
      riskScore: score,
      decision: tier,
      ringId,
      counterfactual:
        tier === 'block'
          ? `Would have been Allowed if amount was ₹${Math.max(200, amount - 2200)} lower.`
          : tier === 'challenge'
          ? 'Verify with OTP — ring membership elevated score from 0.41 to 0.52.'
          : undefined,
      topFeatures:
        tier === 'block'
          ? ['velocity_1h', 'device_reuse', 'bin_risk']
          : tier === 'challenge'
          ? ['velocity_1h', 'geo_mismatch', 'new_device']
          : ['amount_z', 'historical_good'],
      scoredAt: isoMinusMinutes(i * 0.7),
    })
  }
  return out
}

function makeRings() {
  /** @type {import('./types').Ring[]} */
  return [
    {
      id: 'ring_1',
      memberCount: 14,
      density: 0.83,
      sharedAttribute: 'device_fingerprint',
      sharedValue: 'dev_4F:9C:2A',
      status: 'active',
      flaggedAmount: 184_320,
      detectedAt: isoMinusMinutes(38),
      accountIds: Array.from({ length: 14 }, (_, i) => `usr_${pad(i * 11)}`),
    },
    {
      id: 'ring_2',
      memberCount: 7,
      density: 0.71,
      sharedAttribute: 'ip_address',
      sharedValue: '10.42.18.0/24',
      status: 'active',
      flaggedAmount: 96_500,
      detectedAt: isoMinusMinutes(120),
      accountIds: Array.from({ length: 7 }, (_, i) => `usr_${pad(i * 23 + 3)}`),
    },
    {
      id: 'ring_3',
      memberCount: 22,
      density: 0.62,
      sharedAttribute: 'card_bin',
      sharedValue: '457123',
      status: 'review',
      flaggedAmount: 312_750,
      detectedAt: isoMinusHours(4),
      accountIds: Array.from({ length: 22 }, (_, i) => `usr_${pad(i * 5 + 1)}`),
    },
    {
      id: 'ring_4',
      memberCount: 5,
      density: 0.55,
      sharedAttribute: 'shipping_address',
      sharedValue: 'Plot 14, Sector 21, Navi Mumbai',
      status: 'contained',
      flaggedAmount: 41_200,
      detectedAt: isoMinusDays(2),
      accountIds: Array.from({ length: 5 }, (_, i) => `usr_${pad(i * 31 + 7)}`),
    },
  ]
}

function isoMinusHours(h) { return new Date(Date.now() - h * 3_600_000).toISOString() }

function makeAudit() {
  const actions = ['allow', 'challenge', 'block']
  const triggers = ['Model score', 'Ring membership', 'Velocity spike', 'New device + high amount', 'BIN risk list']
  const reasons = [
    'Risk score 0.81 exceeded Block threshold; ring_3 membership confirmed.',
    'Score 0.52 within Challenge band; step-up OTP sent.',
    'Velocity_1h = 12 transactions (peer avg 1.4); blocked.',
    'New device on previously good account; high amount (₹9,800).',
    'BIN 457123 shared with 22 accounts in ring_3.',
    'Score 0.18 — well below Challenge band.',
  ]
  /** @type {import('./types').AuditEntry[]} */
  const out = []
  for (let i = 0; i < 40; i++) {
    const idx = (i * 3) % actions.length
    out.push({
      id: `aud_${i}`,
      timestamp: isoMinusMinutes(i * 1.6),
      transactionId: `txn_${(Date.now() - i * 41_000).toString(36)}`,
      action: /** @type {any} */ (actions[idx].toLowerCase()),
      triggeredBy: pick(triggers, i + 1),
      reasoning: pick(reasons, i + 2),
      user: `usr_${pad((i * 7) % 999)}`,
    })
  }
  return out
}

function makeMetrics() {
  /** @type {import('./types').MetricRow[]} */
  return [
    { tier: 'allow', precision: 0.984, recall: 0.991, f1: 0.987, support: 41_220 },
    { tier: 'challenge', precision: 0.612, recall: 0.554, f1: 0.581, support: 3_104 },
    { tier: 'block', precision: 0.847, recall: 0.789, f1: 0.817, support: 1_240 },
  ]
}

function makeCostCurve() {
  /** @type {import('./types').CostPoint[]} */
  const out = []
  for (let i = 0; i <= 20; i++) {
    const t = i / 20
    const threeTier = 120_000 * Math.exp(-((t - 0.45) ** 2) / 0.04) + 14_000
    const binary = 180_000 * Math.exp(-((t - 0.6) ** 2) / 0.03) + 38_000
    out.push({ threshold: +(t * 100).toFixed(1), threeTier: Math.round(threeTier), binary: Math.round(binary) })
  }
  return out
}

function makeDrift() {
  /** @type {import('./types').DriftPoint[]} */
  const out = []
  for (let i = 30; i >= 0; i--) {
    const base = 0.04 + 0.012 * Math.sin(i / 3.4)
    out.push({ date: isoMinusDays(i).slice(0, 10), psi: +base.toFixed(3), baseline: 0.05 })
  }
  return out
}

function makeFeatureDrift() {
  /** @type {import('./types').FeatureDrift[]} */
  return [
    { feature: 'velocity_1h', score: 0.18, trend: 'up' },
    { feature: 'device_reuse', score: 0.12, trend: 'up' },
    { feature: 'geo_mismatch', score: 0.09, trend: 'flat' },
    { feature: 'bin_risk', score: 0.07, trend: 'down' },
    { feature: 'amount_z', score: 0.05, trend: 'flat' },
  ]
}

function makeDashboardKpis() {
  return {
    scoredToday: 12_847,
    fraudRate: 0.018,
    activeAlerts: 4,
    avgLatencyMs: 38,
    tierBreakdown: { allow: 11_932, challenge: 712, block: 203 },
    ringActivity: 4,
    psiCurrent: 0.062,
    modelVersion: 'xgboost-v2.4.1',
  }
}

function delay(value, ms = 80) {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms))
}

export const api = {
  listTransactions: () => delay(makeTransactions()),
  getTransaction: (id) => delay(makeTransactions().find((t) => t.id === id) || null),
  listRings: () => delay(makeRings()),
  getRing: (id) => delay(makeRings().find((r) => r.id === id) || null),
  listAudit: () => delay(makeAudit()),
  getMetrics: () => delay(makeMetrics()),
  getCostCurve: () => delay(makeCostCurve()),
  getDrift: () => delay(makeDrift()),
  getFeatureDrift: () => delay(makeFeatureDrift()),
  getDashboardKpis: () => delay(makeDashboardKpis()),
  startSimulation: ({ rate, duration, scenario }) =>
    delay({ runId: `sim_${Date.now().toString(36)}`, rate, duration, scenario, startedAt: now().toISOString() }),
}
