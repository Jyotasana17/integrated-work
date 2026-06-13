// API Layer for the Async Execution System Frontend
// Production-grade: NO mock data, NO fallbacks. All data comes from the live backend.
//
// Requests target the SAME-ORIGIN path `/api/v1`, which Next.js (see
// next.config.ts `rewrites`) and Nginx (production) transparently proxy to the
// FastAPI backend. Calling a relative path avoids cross-origin/CORS failures,
// HTTP/HTTPS mismatches, and broken absolute URLs — the historical cause of the
// browser's opaque "Failed to fetch" error. The backend location is configured
// server-side via NEXT_PUBLIC_API_URL (used by the proxy), not in the browser.
const API_BASE_URL = '/api/v1';

// ---------------------------------------------------------------------------
// Auth token storage (localStorage) + helpers
// ---------------------------------------------------------------------------

const ACCESS_KEY = 'tll_access_token';
const REFRESH_KEY = 'tll_refresh_token';
const USER_KEY = 'tll_user';

export interface AuthUser {
  id: string;
  email: string;
  full_name?: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  success: boolean;
  message: string;
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: AuthUser;
}

export const authStore = {
  getAccess: (): string | null => (typeof window !== 'undefined' ? localStorage.getItem(ACCESS_KEY) : null),
  getRefresh: (): string | null => (typeof window !== 'undefined' ? localStorage.getItem(REFRESH_KEY) : null),
  getUser: (): AuthUser | null => {
    if (typeof window === 'undefined') return null;
    const raw = localStorage.getItem(USER_KEY);
    try { return raw ? (JSON.parse(raw) as AuthUser) : null; } catch { return null; }
  },
  set: (access: string, refresh: string, user: AuthUser) => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },
  clear: () => {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
  },
  isAuthenticated: (): boolean => (typeof window !== 'undefined' && !!localStorage.getItem(ACCESS_KEY)),
};

// Attempt to refresh the access token using the stored refresh token.
async function tryRefresh(): Promise<boolean> {
  const refresh = authStore.getRefresh();
  if (!refresh) return false;
  try {
    const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) { authStore.clear(); return false; }
    const data = (await res.json()) as AuthResponse;
    authStore.set(data.access_token, data.refresh_token, data.user);
    return true;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Error Handling
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

// Translate a raw HTTP status into an actionable, human-readable message.
function describeStatus(status: number, detail: string): string {
  switch (status) {
    case 400: return detail || 'Invalid request. Check the data you submitted.';
    case 401: return 'Authentication required. Provide a valid token or API key.';
    case 403: return 'Access denied. You are not authorized for this resource.';
    case 404: return detail || 'Resource not found.';
    case 408: return 'The target server timed out. Try again.';
    case 422: return detail || 'Validation failed. Check the request payload.';
    case 429: return 'Rate limit exceeded. Please slow down and retry.';
    case 502: return 'Backend server is unreachable. Ensure the FastAPI backend is running on port 8000.';
    case 503: return detail || 'A backend dependency (database, Redis, or workers) is unavailable.';
    case 504: return 'The backend gateway timed out while processing the request.';
    default:
      if (status >= 500) return detail || 'The backend encountered an internal error.';
      return detail || `Request failed (HTTP ${status}).`;
  }
}

async function apiFetch<T>(url: string, options: RequestInit = {}, retryOn401 = true): Promise<T> {
  const headers = new Headers(options.headers || {});
  const token = authStore.getAccess();
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  let res: Response;
  try {
    res = await fetch(url, { ...options, headers });
  } catch (e) {
    // A thrown fetch (TypeError "Failed to fetch") is a transport-level failure:
    // the request never reached the backend. Surface an actionable message
    // instead of the opaque browser default.
    throw new ApiError(
      0,
      'Network connection failed: could not reach the backend API. ' +
      'Verify the backend server is running and reachable, then retry.'
    );
  }

  // Access token expired/invalid: try a one-time silent refresh, then retry.
  if (res.status === 401 && retryOn401 && authStore.getRefresh() && !url.includes('/auth/')) {
    const refreshed = await tryRefresh();
    if (refreshed) return apiFetch<T>(url, options, false);
  }

  if (!res.ok) {
    let detail = '';
    try {
      const body = await res.json();
      detail = body.detail || body.message || '';
    } catch { /* response had no JSON body */ }
    throw new ApiError(res.status, describeStatus(res.status, detail));
  }

  // Some endpoints (e.g. 204 No Content) return an empty body.
  if (res.status === 204) return undefined as unknown as T;
  const text = await res.text();
  if (!text) return undefined as unknown as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError(res.status, 'Unable to parse the response from the backend.');
  }
}

// ---------------------------------------------------------------------------
// Interfaces
// ---------------------------------------------------------------------------

export interface Scan {
  id: string;
  name: string;
  target: string;
  status: string;
  config: any;
  created_at: string;
  started_at?: string;
  finished_at?: string;
}

export interface Task {
  id: string;
  scan_id: string;
  method: string;
  url: string;
  headers: any;
  payload: any;
  status: string;
  attempts: number;
  max_retries: number;
  created_at: string;
  response?: {
    id: string;
    status_code: number;
    latency_ms: number;
    response_headers: any;
    response_body: string;
    error_message?: string;
    created_at: string;
  };
}

export interface ScanProgress {
  scan_id: string;
  status: string;
  total_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  pending_tasks: number;
  detailed_stats: {
    QUEUED: number;
    PROCESSING: number;
    RETRYING: number;
    SUCCESS: number;
    FAILED: number;
  };
}

export interface QueueStatus {
  critical_p1: number;
  high_p2: number;
  medium_p3: number;
  low_p4: number;
  delayed_retries: number;
  dead_letters: number;
  total_pending: number;
}

export interface WorkerStatus {
  active_workers: number;
  status: string;
  workers: string[];
}

export interface ExecutionStats {
  throughput: {
    total_processed: number;
    success: number;
    failure: number;
    rate_limited_429: number;
  };
  rates: {
    success_rate_pct: number;
    failure_rate_pct: number;
    rate_limit_pct: number;
  };
  retries_total: number;
}

export interface JWTAnalysisResult {
  valid: boolean;
  header: any;
  payload: any;
  vulnerabilities: Array<{
    severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
    type: string;
    description: string;
    remediation: string;
  }>;
  risk_score: number;
  error?: string;
}

export interface DiffResult {
  status_differs: boolean;
  status_a: number;
  status_b: number;
  body_length_differs: boolean;
  body_length_a: number;
  body_length_b: number;
  json_diff_keys: string[];
  leak_detected: boolean;
  leak_type: string | null;
  risk_score: number;
  explanation: string;
}

export interface Vulnerability {
  id: string;
  title: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  path: string;
  method: string;
  description: string;
  remediation: string;
  cvss: number;
  impact: string;
  evidence?: any;
}

export interface DashboardStats {
  total_scans: number;
  running_scans: number;
  completed_scans: number;
  failed_scans: number;
  total_endpoints: number;
  total_vulnerabilities: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  security_score: number;
  risk_score: number;
  recent_activity: Array<{
    task_id: string;
    method: string;
    url: string;
    status: string;
    status_code?: number;
    timestamp: string;
  }>;
}

export interface RoleSwapResult {
  endpoint: string;
  method: string;
  source_role: string;
  target_role: string;
  status: string;
  bypass: boolean;
  detail: string;
  source_status_code?: number;
  target_status_code?: number;
}

export interface TimelinePoint {
  timestamp: string;
  requests: number;
  latency: number;
  failures: number;
  queue_depth: number;
}

export interface CopilotResponse {
  answer: string;
  evidence: any[];
  suggestions: string[];
}

// ---------------------------------------------------------------------------
// API Service — All methods hit live backend, no mock fallbacks
// ---------------------------------------------------------------------------

export const apiService = {
  // ---- Auth ----

  async register(email: string, password: string, fullName?: string): Promise<AuthResponse> {
    const data = await apiFetch<AuthResponse>(`${API_BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, full_name: fullName }),
    });
    authStore.set(data.access_token, data.refresh_token, data.user);
    return data;
  },

  async login(email: string, password: string): Promise<AuthResponse> {
    const data = await apiFetch<AuthResponse>(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    authStore.set(data.access_token, data.refresh_token, data.user);
    return data;
  },

  async logout(): Promise<void> {
    const refresh = authStore.getRefresh();
    try {
      if (refresh) {
        await fetch(`${API_BASE_URL}/auth/logout`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refresh }),
        });
      }
    } finally {
      authStore.clear();
    }
  },

  async getMe(): Promise<AuthUser> {
    return apiFetch<AuthUser>(`${API_BASE_URL}/auth/me`);
  },

  async listUsers(): Promise<AuthUser[]> {
    return apiFetch<AuthUser[]>(`${API_BASE_URL}/auth/users`);
  },

  // ---- Scans ----

  async getScans(): Promise<Scan[]> {
    return apiFetch<Scan[]>(`${API_BASE_URL}/scans`);
  },

  async createScan(name: string, target: string, config: any = {}): Promise<Scan> {
    return apiFetch<Scan>(`${API_BASE_URL}/scans`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, target, config }),
    });
  },

  async deleteScan(scanId: string): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/scans/${scanId}`, { method: 'DELETE' });
    if (!res.ok) {
      throw new ApiError(res.status, 'Failed to delete scan');
    }
  },

  async getScanProgress(scanId: string): Promise<ScanProgress> {
    return apiFetch<ScanProgress>(`${API_BASE_URL}/scans/${scanId}/progress`);
  },

  async getScanTasks(scanId: string): Promise<Task[]> {
    return apiFetch<Task[]>(`${API_BASE_URL}/scans/${scanId}/tasks`);
  },

  // ---- Discovery ----

  async runDiscovery(scanId: string, specSource: string, baseUrl?: string): Promise<any> {
    return apiFetch<any>(`${API_BASE_URL}/scans/${scanId}/discover`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ spec_source: specSource, base_url: baseUrl }),
    });
  },

  // ---- Queue / Workers / Execution ----

  async getQueueStatus(): Promise<QueueStatus> {
    return apiFetch<QueueStatus>(`${API_BASE_URL}/queue/status`);
  },

  async getWorkerStatus(): Promise<WorkerStatus> {
    return apiFetch<WorkerStatus>(`${API_BASE_URL}/workers/status`);
  },

  async getExecutionStats(): Promise<ExecutionStats> {
    return apiFetch<ExecutionStats>(`${API_BASE_URL}/execution/stats`);
  },

  // ---- Reports ----

  async getReport(scanId: string, format: string = 'json', type: string = 'technical'): Promise<any> {
    return apiFetch<any>(`${API_BASE_URL}/scans/${scanId}/report?format=${format}&type=${type}`);
  },

  // ---- JWT ----

  async analyzeJWT(token: string): Promise<JWTAnalysisResult> {
    return apiFetch<JWTAnalysisResult>(`${API_BASE_URL}/jwt/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    });
  },

  // ---- Diff ----

  async runDiff(respA: { status_code: number, body: string }, respB: { status_code: number, body: string }): Promise<DiffResult> {
    return apiFetch<DiffResult>(`${API_BASE_URL}/diff`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ response_a: respA, response_b: respB }),
    });
  },

  // ---- Dashboard Stats ----

  async getDashboardStats(): Promise<DashboardStats> {
    return apiFetch<DashboardStats>(`${API_BASE_URL}/dashboard/stats`);
  },

  // ---- Vulnerabilities ----

  async getVulnerabilities(scanId: string): Promise<Vulnerability[]> {
    return apiFetch<Vulnerability[]>(`${API_BASE_URL}/scans/${scanId}/vulnerabilities`);
  },

  // ---- Role Swap Results ----

  async getRoleSwapResults(scanId: string): Promise<RoleSwapResult[]> {
    return apiFetch<RoleSwapResult[]>(`${API_BASE_URL}/scans/${scanId}/role-swaps`);
  },

  // ---- Scan Timeline (for live charts) ----

  async getScanTimeline(scanId: string): Promise<TimelinePoint[]> {
    return apiFetch<TimelinePoint[]>(`${API_BASE_URL}/scans/${scanId}/timeline`);
  },

  // ---- AI Copilot ----

  async askCopilot(scanId: string | undefined, query: string, contextView: string): Promise<CopilotResponse> {
    return apiFetch<CopilotResponse>(`${API_BASE_URL}/copilot/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scan_id: scanId, query, context_view: contextView }),
    });
  },

  // ---- SSE Stream Subscription ----

  subscribeScanStream(scanId: string, onMessage: (data: any) => void): EventSource {
    const source = new EventSource(`${API_BASE_URL}/stream/scan/${scanId}`);
    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch { /* ignore parse errors */ }
    };
    return source;
  }
};
