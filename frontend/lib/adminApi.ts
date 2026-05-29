// Admin control-plane client. Auth is an httpOnly session cookie set by the
// backend's Discord OAuth callback; we just send credentials on every request.
// The admin route is never linked from the public nav.

// All admin requests go through the Vercel rewrite at /api/admin/* (see
// next.config.ts). This makes the session cookie set by the OAuth callback
// first-party to the Vercel origin, so browsers send it back on subsequent
// XHR — cross-site cookie blocking would otherwise drop it silently.
const API_BASE = "/api/admin";

export const discordLoginUrl = (): string => `${API_BASE}/auth/discord/login`;

export interface AuthMe {
  authenticated: boolean;
  discord_id?: string;
  username?: string;
  exp?: number;
}

export interface Progress {
  run_id: number;
  total: number;
  pending: number;
  running: number;
  done: number;
  failed: number;
  dead: number;
  skipped: number;
  terminal: number;
  pages: number;
  sitemap_total: number;
  last_heartbeat: string | null;
  current_municipality: string | null;
  pct: number;
}

export type RunState =
  | "active" | "stale" | "orphaned" | "paused" | "stopped" | "cancelled" | "done";

export interface RunSummary {
  id: number;
  status: string | null;
  state: RunState;
  mode: string | null;
  worker_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  last_heartbeat: string | null;
  heartbeat_age_min: number | null;
  duration_seconds: number | null;
  pages_per_min: number | null;
  progress: Progress;
}

export interface Worker {
  worker_id: string;
  active_tasks: number;
  last_heartbeat: string | null;
  heartbeat_age_min: number | null;
  alive: boolean;
}

export interface PlatformJob {
  id: string;
  name: string;
  status: "QUEUED" | "RUNNING" | "PAUSED" | "DRAINING" | "COMPLETED" | "FAILED" | "CANCELED";
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  // List-endpoint flat fields
  pagesFetched?: number;
  errorCount?: number;
  // Detail-endpoint nested fields (present when fetched individually)
  stats?: {
    pagesDiscovered: number;
    pagesFetched: number;
    pagesExtracted: number;
    errors: number;
    bytesFetched: number;
  };
}

export interface PlatformInfo {
  ok: boolean;
  url: string;
  active_count?: number;
  active_jobs?: PlatformJob[];
  recent_jobs?: PlatformJob[];
  error?: string;
}

export interface PlatformError {
  id: string;
  jobId: string;
  taskId: string | null;
  pageId: string | null;
  stage: string;       // fetch | render | extract | embed
  code: string;        // SSRF:dns-empty | RETRY_EXHAUSTED | TOO_LARGE | ...
  message: string;
  details: string | null;
  attempt: number;
  terminal: boolean;
  occurredAt: string;
}

export interface PlatformErrorsResult {
  ok: boolean;
  count?: number;
  by_code?: Record<string, number>;
  errors: PlatformError[];
  error?: string;
}

export interface PlatformJobDetail extends PlatformJob {
  ok: boolean;
  stats?: {
    pagesDiscovered: number;
    pagesFetched: number;
    pagesExtracted: number;
    errors: number;
    bytesFetched: number;
  };
  tasksByStatus?: Record<string, number>;
  frontier?: { depth: number };
  error?: string;
}

export interface Overview {
  generated_at: string;
  system: {
    db_ok: boolean;
    backend: string;
    stale_minutes: number;
    dispatch_configured: boolean;
    platform_url?: string;
    environment: Record<string, string | boolean>;
  };
  coverage: {
    municipalities_indexed: number;
    municipalities_total: number;
    coverage_pct: number;
    total_pages: number;
    total_documents: number;
  };
  runs_by_state: Record<string, number>;
  active_run: RunSummary | null;
  last_success: RunSummary | null;
  last_failed: RunSummary | null;
  workers: { count: number; alive: number; list: Worker[] };
  platform?: PlatformInfo;
}

export interface TaskRow {
  id: number;
  run_id: number;
  municipality_id: string;
  name: string | null;
  province: string | null;
  mode: string;
  status: string;
  attempts: number;
  max_attempts: number;
  leased_by: string | null;
  lease_expires_at: string | null;
  heartbeat: string | null;
  pages_found: number;
  sitemap_total: number;
  completeness_pct: number;
  error: string | null;
  created_at: string;
  updated_at: string;
  duration_seconds: number | null;
  heartbeat_age_min: number | null;
  lease_expired: boolean;
}

export interface LogEvent {
  id: number;
  run_id: number | null;
  task_id: number | null;
  municipality_id: string | null;
  level: string;
  event: string;
  message: string | null;
  meta: Record<string, unknown> | null;
  created_at: string;
}

export class AdminError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  // path values come in like "/admin/overview" — strip the leading "/admin"
  // since API_BASE already maps to it via the Vercel rewrite.
  const subpath = path.startsWith("/admin") ? path.slice("/admin".length) : path;
  const res = await fetch(`${API_BASE}${subpath}`, {
    ...init,
    cache: "no-store",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-json */
    }
    throw new AdminError(res.status, String(detail));
  }
  return res.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown) =>
  call<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });

export const adminApi = {
  me: () => call<AuthMe>("/admin/auth/me"),
  logout: () => call<void>("/admin/auth/logout", { method: "POST" }),
  overview: () => call<Overview>("/admin/overview"),
  runs: (limit = 25) => call<RunSummary[]>(`/admin/runs?limit=${limit}`),
  tasks: (runId: number) => call<TaskRow[]>(`/admin/runs/${runId}/tasks`),
  logs: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== "") qs.set(k, String(v));
    }
    return call<LogEvent[]>(`/admin/logs?${qs.toString()}`);
  },

  start: (body: { mode: string; only_missing: boolean; force: boolean; dispatch: boolean }) =>
    post<{
      ok: boolean;
      run_id?: number;
      job_map?: Record<string, string>;
      count?: number;
      reason?: string;
      source?: "platform" | "legacy";
    }>("/admin/crawl/start", body),
  pause: (id: number) => post(`/admin/crawl/${id}/pause`),
  resume: (id: number) => post(`/admin/crawl/${id}/resume`),
  stop: (id: number) => post(`/admin/crawl/${id}/stop`),
  cancel: (id: number) => post(`/admin/crawl/${id}/cancel`),
  reset: (id: number) => post(`/admin/crawl/${id}/reset`),
  reap: (id: number) => post(`/admin/crawl/${id}/reap`),
  retryFailed: (id: number) => post(`/admin/crawl/${id}/retry-failed`),
  clearLocks: (id?: number) => post(`/admin/crawl/clear-locks${id ? `?run_id=${id}` : ""}`),
  killOrphans: () => post("/admin/crawl/kill-orphans"),

  retryTask: (taskId: number) => post(`/admin/tasks/${taskId}/retry`),
  resetTask: (taskId: number) => post(`/admin/tasks/${taskId}/reset`),
  skipMuni: (runId: number, muni: string) =>
    post(`/admin/runs/${runId}/municipalities/${muni}/skip`),
  recrawl: (muni: string, mode = "discover") =>
    post(`/admin/municipalities/${muni}/recrawl`, { mode, dispatch: true }),

  platformJobs: (limit = 20) =>
    call<PlatformJob[]>(`/admin/platform/jobs?limit=${limit}`),
  platformJobDetail: (jobId: string) =>
    call<PlatformJobDetail>(`/admin/platform/jobs/${jobId}`),
  platformJobErrors: (jobId: string, limit = 50) =>
    call<PlatformErrorsResult>(`/admin/platform/jobs/${jobId}/errors?limit=${limit}`),
  cancelPlatformJob: (jobId: string) =>
    post(`/admin/platform/jobs/${jobId}/cancel`),
};
