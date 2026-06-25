// API Layer for the Async Execution System Frontend
// Production-grade: NO mock data, NO fallbacks. All data comes from the live backend.
const apiHost = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "";
const API_BASE_URL = apiHost
  ? apiHost.endsWith("/api/v1")
    ? apiHost
    : `${apiHost}/api/v1`
  : "/api/v1";

function buildApiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
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

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, options);
  } catch (error: any) {
    const detail = getNetworkErrorDetail(error);
    throw new ApiError(0, detail);
  }

  if (!res.ok) {
    let detail = '';
    try {
      const body = await res.json();
      detail = body.detail || body.message || detail;
    } catch {
      if (res.status === 204) {
        return {} as T;
      }
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) {
    return {} as T;
  }

  const contentType = res.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return {} as T;
  }

  return res.json();
}

function getNetworkErrorDetail(error: any): string {
  const message = error?.message || String(error) || "Network request failed.";
  if (message.includes("Failed to fetch")) {
    return "Unable to connect to the backend. Verify the API server is running, the URL is correct, and CORS is configured.";
  }
  if (message.includes("NetworkError")) {
    return "Network error while contacting the backend. Check your connection and proxy settings.";
  }
  return message;
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
  mutation_strategy: string | null;
  mutation_reason: string | null;
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
    return apiFetch<Scan[]>(buildApiUrl('/scans'));
  },

  async createScan(name: string, target: string, config: any = {}): Promise<Scan> {
    return apiFetch<Scan>(buildApiUrl('/scans'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, target, config }),
    });
  },

  async deleteScan(scanId: string): Promise<void> {
    const res = await fetch(buildApiUrl(`/scans/${scanId}`), { method: 'DELETE' });
    if (!res.ok) {
      throw new ApiError(res.status, 'Failed to delete scan');
    }
  },

  async getScanProgress(scanId: string): Promise<ScanProgress> {
    return apiFetch<ScanProgress>(buildApiUrl(`/scans/${scanId}/progress`));
  },

  async getScanTasks(scanId: string): Promise<Task[]> {
    return apiFetch<Task[]>(buildApiUrl(`/scans/${scanId}/tasks`));
  },

  // ---- Discovery ----

  async runDiscovery(scanId: string, specSource: string, baseUrl?: string): Promise<any> {
    return apiFetch<any>(buildApiUrl(`/scans/${scanId}/discover`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ spec_source: specSource, base_url: baseUrl }),
    });
  },

  // ---- Queue / Workers / Execution ----

  async getQueueStatus(): Promise<QueueStatus> {
    return apiFetch<QueueStatus>(buildApiUrl('/queue/status'));
  },

  async getWorkerStatus(): Promise<WorkerStatus> {
    return apiFetch<WorkerStatus>(buildApiUrl('/workers/status'));
  },

  async getExecutionStats(): Promise<ExecutionStats> {
    return apiFetch<ExecutionStats>(buildApiUrl('/execution/stats'));
  },

  // ---- Reports ----

  async getReport(scanId: string, format: string = 'json', type: string = 'technical'): Promise<any> {
    return apiFetch<any>(buildApiUrl(`/scans/${scanId}/report?format=${encodeURIComponent(format)}&type=${encodeURIComponent(type)}`));
  },

  // ---- JWT ----

  async analyzeJWT(token: string): Promise<JWTAnalysisResult> {
    return apiFetch<JWTAnalysisResult>(buildApiUrl('/jwt/analyze'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    });
  },

  // ---- Diff ----

  async runDiff(respA: { status_code: number, body: string }, respB: { status_code: number, body: string }): Promise<DiffResult> {
    return apiFetch<DiffResult>(buildApiUrl('/diff'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ response_a: respA, response_b: respB }),
    });
  },

  // ---- Dashboard Stats ----

  async getDashboardStats(): Promise<DashboardStats> {
    return apiFetch<DashboardStats>(buildApiUrl('/dashboard/stats'));
  },

  // ---- Vulnerabilities ----

  async getVulnerabilities(scanId: string): Promise<Vulnerability[]> {
    return apiFetch<Vulnerability[]>(buildApiUrl(`/scans/${scanId}/vulnerabilities`));
  },

  // ---- Role Swap Results ----

  async getRoleSwapResults(scanId: string): Promise<RoleSwapResult[]> {
    return apiFetch<RoleSwapResult[]>(buildApiUrl(`/scans/${scanId}/role-swaps`));
  },

  // ---- Scan Timeline (for live charts) ----

  async getScanTimeline(scanId: string): Promise<TimelinePoint[]> {
    return apiFetch<TimelinePoint[]>(buildApiUrl(`/scans/${scanId}/timeline`));
  },

  // ---- AI Copilot ----

  async askCopilot(scanId: string | undefined, query: string, contextView: string): Promise<CopilotResponse> {
    return apiFetch<CopilotResponse>(buildApiUrl('/copilot/ask'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scan_id: scanId, query, context_view: contextView }),
    });
  },

  // ---- SSE Stream Subscription ----

  subscribeScanStream(scanId: string, onMessage: (data: any) => void): EventSource {
    const source = new EventSource(buildApiUrl(`/stream/scan/${scanId}`));
    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch { /* ignore parse errors */ }
    };
    return source;
  }
};
