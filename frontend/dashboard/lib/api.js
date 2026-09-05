const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000/api/v1';

function token() {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('spark_access_token');
}

function formatApiError(body, status) {
  const detail = body && body.detail;
  if (typeof detail === 'string' && detail) return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((item) => (item && item.msg) || (typeof item === 'string' ? item : null))
      .filter(Boolean)
      .join(' ')
      || `API request failed: ${status}`;
  }
  return `API request failed: ${status}`;
}

async function handleResponse(response) {
  if (response.status === 401 && typeof window !== 'undefined') {
    localStorage.removeItem('spark_access_token');
    localStorage.removeItem('spark_refresh_token');
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(formatApiError(body, response.status));
  return body;
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const access = token();
  if (access) headers.set('Authorization', `Bearer ${access}`);
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  return handleResponse(await fetch(`${API_BASE}${path}`, { ...options, headers, cache: 'no-store' }));
}

export const api = {
  login: (payload) => request('/auth/login', { method:'POST', body:JSON.stringify(payload) }),
  signup: (payload) => request('/auth/signup', { method:'POST', body:JSON.stringify(payload) }),
  refresh: (refresh_token) => request('/auth/refresh', { method:'POST', body:JSON.stringify({refresh_token}) }),
  logout: (refresh_token) => request('/auth/logout', { method:'POST', body:JSON.stringify({refresh_token}) }),
  me: () => request('/auth/me'),
  listTransactions: (params={}) => request(`/transactions?${new URLSearchParams(params)}`),
  getTransaction: (id) => request(`/transactions/${encodeURIComponent(id)}`),
  listRings: (params={}) => request(`/rings?${new URLSearchParams(params)}`),
  getRing: (id) => request(`/rings/${encodeURIComponent(id)}`),
  getRingGraph: (id) => request(`/rings/${encodeURIComponent(id)}/graph`),
  listAudit: (params={}) => request(`/audit?${new URLSearchParams(params)}`),
  getModelHealth: () => request('/model/health'),
  updateThresholds: (payload) => request('/model/health/thresholds', {method:'PUT',body:JSON.stringify(payload)}),
  getMetrics: () => request('/analytics/metrics'),
  getCostCurve: () => request('/analytics/cost-curve'),
  getDashboardKpis: () => request('/analytics/kpis'),
  scoreTransaction: (payload) => request('/score', {method:'POST',body:JSON.stringify(payload)}),
  startSimulation: (payload) => request('/simulation/start', {method:'POST',body:JSON.stringify(payload)}),
  reloadModel: () => request('/model/health/reload', {method:'POST'}),
};
