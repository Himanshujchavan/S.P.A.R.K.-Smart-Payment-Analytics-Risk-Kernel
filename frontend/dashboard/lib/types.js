// Shared types for S.P.A.R.K. dashboard. Kept as JSDoc typedefs so they are
// useful from both .jsx and .tsx without a separate build step.

/**
 * @typedef {'allow' | 'challenge' | 'block'} Tier
 * @typedef {'upi' | 'card' | 'netbanking' | 'wallet' | 'emandate'} PaymentMethod
 */

/**
 * @typedef {Object} Transaction
 * @property {string} id
 * @property {string} userId
 * @property {string} merchantId
 * @property {number} amount
 * @property {string} currency
 * @property {PaymentMethod} method
 * @property {string} cardBin
 * @property {string} deviceFingerprint
 * @property {string} ipAddress
 * @property {string} city
 * @property {number} riskScore
 * @property {Tier} decision
 * @property {string} [ringId]
 * @property {string} [counterfactual]
 * @property {string[]} [topFeatures]
 * @property {string} scoredAt
 */

/**
 * @typedef {Object} Ring
 * @property {string} id
 * @property {number} memberCount
 * @property {number} density
 * @property {string} sharedAttribute
 * @property {string} sharedValue
 * @property {string} status
 * @property {number} flaggedAmount
 * @property {string} detectedAt
 * @property {string[]} accountIds
 */

/**
 * @typedef {Object} AuditEntry
 * @property {string} id
 * @property {string} timestamp
 * @property {string} transactionId
 * @property {Tier} action
 * @property {string} triggeredBy
 * @property {string} reasoning
 * @property {string} user
 */

/**
 * @typedef {Object} MetricRow
 * @property {Tier} tier
 * @property {number} precision
 * @property {number} recall
 * @property {number} f1
 * @property {number} support
 */

/**
 * @typedef {Object} CostPoint
 * @property {number} threshold
 * @property {number} threeTier
 * @property {number} binary
 */

/**
 * @typedef {Object} DriftPoint
 * @property {string} date
 * @property {number} psi
 * @property {number} baseline
 */

/**
 * @typedef {Object} FeatureDrift
 * @property {string} feature
 * @property {number} score
 * @property {'up' | 'down' | 'flat'} trend
 */

export const TIER_META = {
  allow: { label: 'Allowed', color: 'var(--risk-allow)' },
  challenge: { label: 'Challenged', color: 'var(--risk-challenge)' },
  block: { label: 'Blocked', color: 'var(--risk-block)' },
}
