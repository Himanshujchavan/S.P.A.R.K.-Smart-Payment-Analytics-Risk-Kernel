// Centralized API client for the S.P.A.R.K. dashboard.
// All calls are routed to the FastAPI backend.

const API_BASE = 'http://localhost:8000/api/v1';

async function handleResponse(response) {
  if (!response.ok) {
    throw new Error(`API request failed: ${response.statusText}`);
  }
  return response.json();
}

export const api = {
  // --- Transactions ---
  listTransactions: async (params = {}) => {
    const q = new URLSearchParams(params).toString();
    const resp = await fetch(`${API_BASE}/transactions?${q}`);
    return handleResponse(resp);
  },
  getTransaction: async (id) => {
    const resp = await fetch(`${API_BASE}/transactions/${id}`);
    return handleResponse(resp);
  },

  // --- Abuse Rings ---
  listRings: async (params = {}) => {
    const q = new URLSearchParams(params).toString();
    const resp = await fetch(`${API_BASE}/rings?${q}`);
    return handleResponse(resp);
  },
  getRing: async (id) => {
    const resp = await fetch(`${API_BASE}/rings/${id}`);
    return handleResponse(resp);
  },
  getRingGraph: async (id) => {
    const resp = await fetch(`${API_BASE}/rings/${id}/graph`);
    return handleResponse(resp);
  },

  // --- Audit & Compliance ---
  listAudit: async (params = {}) => {
    const q = new URLSearchParams(params).toString();
    const resp = await fetch(`${API_BASE}/audit?${q}`);
    return handleResponse(resp);
  },

  // --- Analytics & Model Health ---
  getModelHealth: async () => {
    const resp = await fetch(`${API_BASE}/model/health`);
    return handleResponse(resp);
  },
  getMetrics: async () => {
    const resp = await fetch(`${API_BASE}/analytics/metrics`);
    return handleResponse(resp);
  },
  getCostCurve: async () => {
    const resp = await fetch(`${API_BASE}/analytics/cost-curve`);
    return handleResponse(resp);
  },
  getDashboardKpis: async () => {
    const resp = await fetch(`${API_BASE}/analytics/kpis`);
    return handleResponse(resp);
  },

  // --- Scoring & Simulation ---
  scoreTransaction: async (payload) => {
    const resp = await fetch(`${API_BASE}/score`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(resp);
  },
  startSimulation: async (payload) => {
    const resp = await fetch(`${API_BASE}/simulation/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(resp);
  },

  // --- Admin ---
  reloadModel: async () => {
    const resp = await fetch(`${API_BASE}/model/health/reload`, {
      method: 'POST',
    });
    return handleResponse(resp);
  }
};
