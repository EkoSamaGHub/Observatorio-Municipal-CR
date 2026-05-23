"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity, AlertTriangle, Database, Lock, LogOut, Pause, Play,
  RefreshCw, Server, ShieldCheck, Skull, Unlock,
} from "lucide-react";
import {
  adminApi, AdminError, discordLoginUrl,
  type Overview, type RunSummary,
} from "@/lib/adminApi";
import {
  ActionButton, Card, ProgressBar, RunStateBadge, Stat, fmtDuration, relTime,
} from "@/components/admin/ui";
import RunsPanel from "@/components/admin/RunsPanel";
import LogsPanel from "@/components/admin/LogsPanel";

const REFRESH_MS = 5000;

export default function AdminPage() {
  // null = still probing; false = not signed in; true = session is valid.
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [probeError, setProbeError] = useState<string | null>(null);

  const probe = useCallback(async () => {
    try {
      const me = await adminApi.me();
      setAuthed(me.authenticated);
      setProbeError(null);
    } catch (err) {
      const e = err as AdminError;
      setAuthed(false);
      setProbeError(
        e.status === 503 ? "Admin is disabled on the server (ADMIN_TOKEN not set)."
        : `Could not reach the admin API: ${e.message}`
      );
    }
  }, []);

  useEffect(() => { probe(); }, [probe]);

  async function logout() {
    try { await adminApi.logout(); } catch { /* clear UI even if request fails */ }
    setAuthed(false);
  }

  if (authed === null) return null;
  if (!authed) return <Login error={probeError} />;
  return <Dashboard onLogout={logout} />;
}

// ── login gate ──────────────────────────────────────────────────────────────

function Login({ error }: { error: string | null }) {
  return (
    <div className="max-w-sm mx-auto mt-16">
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-9 h-9 rounded-lg bg-blue-900 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-slate-800">Admin control center</h1>
            <p className="text-xs text-slate-400">Crawler operations</p>
          </div>
        </div>
        {error && <p className="text-xs text-rose-600 mb-3">{error}</p>}
        <a
          href={discordLoginUrl()}
          className="w-full inline-flex items-center justify-center gap-2 bg-[#5865F2] hover:bg-[#4752c4] text-white font-semibold rounded-lg py-2 text-sm">
          {/* Discord logo */}
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M20.317 4.369A19.79 19.79 0 0 0 16.558 3a.074.074 0 0 0-.079.037 13.83 13.83 0 0 0-.61 1.25 18.27 18.27 0 0 0-5.487 0 12.65 12.65 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.74 19.74 0 0 0 5.93 4.369a.07.07 0 0 0-.032.027C2.533 9.043 1.616 13.58 2.066 18.057a.082.082 0 0 0 .031.056 19.9 19.9 0 0 0 5.993 3.03.077.077 0 0 0 .084-.027 14.2 14.2 0 0 0 1.226-1.994.075.075 0 0 0-.041-.104 13.1 13.1 0 0 1-1.872-.892.077.077 0 0 1-.008-.128c.126-.094.252-.192.371-.292a.074.074 0 0 1 .078-.01c3.927 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .079.009c.12.1.245.199.372.293a.077.077 0 0 1-.006.128 12.3 12.3 0 0 1-1.873.891.076.076 0 0 0-.04.105c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.84 19.84 0 0 0 6.002-3.03.077.077 0 0 0 .031-.055c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.028zM8.02 15.331c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.974 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
          </svg>
          Sign in with Discord
        </a>
        <p className="text-[11px] text-slate-400 mt-3 text-center">
          Only allowlisted Discord accounts can access this control center.
        </p>
      </Card>
    </div>
  );
}

// ── dashboard ─────────────────────────────────────────────────────────────

function Dashboard({ onLogout }: { onLogout: () => void }) {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [auto, setAuto] = useState(true);
  const [toast, setToast] = useState<{ ok: boolean; msg: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const notify = useCallback((ok: boolean, msg: string) => {
    setToast({ ok, msg });
    setTimeout(() => setToast(null), 4000);
  }, []);

  const refresh = useCallback(() => {
    Promise.all([adminApi.overview(), adminApi.runs(25)])
      .then(([o, r]) => { setOverview(o); setRuns(r); setErr(null); })
      .catch((e: AdminError) => {
        if (e.status === 401) { onLogout(); }
        else setErr(e.message);
      });
  }, [onLogout]);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    if (!auto) return;
    const id = setInterval(refresh, REFRESH_MS);
    return () => clearInterval(id);
  }, [auto, refresh]);

  if (!overview) {
    return <div className="text-center py-20 text-slate-400">{err ?? "Loading control center…"}</div>;
  }

  const cov = overview.coverage;
  const active = overview.active_run;

  return (
    <div className="space-y-4">
      {/* header */}
      <div className="flex flex-wrap items-center gap-3 justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-blue-900 flex items-center justify-center">
            <Server className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-slate-800 leading-tight">Crawler control center</h1>
            <p className="text-[11px] text-slate-400">updated {relTime(overview.generated_at)}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setAuto((a) => !a)}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold ${
              auto ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>
            {auto ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            Auto {auto ? "on" : "off"}
          </button>
          <button onClick={refresh}
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold bg-slate-100 text-slate-600 hover:bg-slate-200">
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
          <button onClick={onLogout}
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold bg-slate-100 text-slate-600 hover:bg-slate-200">
            <LogOut className="w-3.5 h-3.5" /> Logout
          </button>
        </div>
      </div>

      {err && (
        <div className="flex items-center gap-2 rounded-lg bg-rose-50 text-rose-700 px-4 py-2 text-sm">
          <AlertTriangle className="w-4 h-4" /> {err}
        </div>
      )}

      {/* system health strip */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 bg-white border border-slate-200 rounded-xl px-4 py-2.5">
        <span className="inline-flex items-center gap-1.5">
          <Database className="w-3.5 h-3.5" />
          DB <b className={overview.system.db_ok ? "text-emerald-600" : "text-rose-600"}>
            {overview.system.db_ok ? "ok" : "down"}</b> ({overview.system.backend})
        </span>
        <span className="inline-flex items-center gap-1.5">
          dispatch{" "}
          <b className={overview.system.dispatch_configured ? "text-emerald-600" : "text-slate-400"}>
            {overview.system.dispatch_configured ? "configured" : "manual"}</b>
        </span>
        {Object.entries(overview.system.environment).map(([k, v]) => (
          <span key={k} className="text-slate-400">{k.replace(/^RAILWAY_/, "")}=<b className="text-slate-600">{String(v)}</b></span>
        ))}
      </div>

      {/* stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Indexed" value={`${cov.municipalities_indexed}/${cov.municipalities_total}`}
          sub={`${cov.coverage_pct}% coverage`} tone="blue" />
        <Stat label="Pages" value={cov.total_pages.toLocaleString("es-CR")}
          sub={`${cov.total_documents.toLocaleString("es-CR")} documents`} />
        <Stat label="Workers" value={`${overview.workers.alive}/${overview.workers.count}`}
          sub="alive / leasing" tone={overview.workers.alive > 0 ? "emerald" : "slate"} />
        <Stat label="Active run" value={active ? `#${active.id}` : "none"}
          sub={active ? active.state : "idle"} tone={active ? "emerald" : "slate"} />
      </div>

      <ActiveRunPanel active={active} toast={notify} refresh={refresh} />

      <ControlPanel overview={overview} toast={notify} refresh={refresh} />

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <RunsPanel runs={runs} toast={notify} refresh={refresh} />
        <LogsPanel toast={notify} auto={auto} />
      </div>

      {/* toast */}
      {toast && (
        <div className={`fixed bottom-4 right-4 z-50 rounded-lg px-4 py-2.5 text-sm font-medium shadow-lg ${
          toast.ok ? "bg-emerald-600 text-white" : "bg-rose-600 text-white"}`}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}

function ActiveRunPanel({ active, toast, refresh }: {
  active: RunSummary | null; toast: (ok: boolean, m: string) => void; refresh: () => void;
}) {
  if (!active) {
    return (
      <Card className="px-5 py-4 flex items-center gap-2 text-sm text-slate-500">
        <span className="w-2 h-2 rounded-full bg-slate-300" /> No active crawl. Start one below.
      </Card>
    );
  }
  const p = active.progress;
  const wrap = (fn: () => Promise<unknown>) => async () => { await fn(); refresh(); };
  const isPaused = active.state === "paused";
  return (
    <Card className="p-5 space-y-3 border-blue-200">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-blue-600" />
          <span className="font-bold text-slate-800">Run #{active.id}</span>
          <RunStateBadge state={active.state} />
          <span className="text-xs text-slate-400">{active.mode}</span>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span>{fmtDuration(active.duration_seconds)} elapsed</span>
          {active.pages_per_min != null && <span>{active.pages_per_min} pages/min</span>}
          {active.state === "stale" && (
            <span className="text-amber-600 font-semibold">no heartbeat for {active.heartbeat_age_min}m</span>
          )}
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
          <span>{p.terminal}/{p.total} municipalities · {p.pct}%</span>
          <span>{p.pages.toLocaleString("es-CR")} pages this run</span>
        </div>
        <ProgressBar pct={p.pct} tone={active.state === "active" ? "emerald" : "blue"} />
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500 mt-2">
          <span>pending {p.pending}</span><span>running {p.running}</span>
          <span>done {p.done}</span><span className="text-amber-600">failed {p.failed}</span>
          <span className="text-rose-600">dead {p.dead}</span><span>skipped {p.skipped}</span>
          {p.current_municipality && <span className="font-semibold text-slate-700">now: {p.current_municipality}</span>}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5 pt-1 border-t border-slate-100">
        {isPaused
          ? <ActionButton label="Resume" onAction={wrap(() => adminApi.resume(active.id))} onResult={toast} />
          : <ActionButton label="Pause" onAction={wrap(() => adminApi.pause(active.id))} onResult={toast} />}
        <ActionButton label="Stop" onAction={wrap(() => adminApi.stop(active.id))} onResult={toast} confirm />
        <ActionButton label="Reap stale" onAction={wrap(() => adminApi.reap(active.id))} onResult={toast} />
        <ActionButton label="Clear locks" onAction={wrap(() => adminApi.clearLocks(active.id))} onResult={toast} />
        <ActionButton label="Retry failed" onAction={wrap(() => adminApi.retryFailed(active.id))} onResult={toast} />
        <ActionButton label="Force reset" onAction={wrap(() => adminApi.reset(active.id))} onResult={toast} confirm danger />
        <ActionButton label="Cancel run" onAction={wrap(() => adminApi.cancel(active.id))} onResult={toast} confirm danger />
      </div>
    </Card>
  );
}

function ControlPanel({ overview, toast, refresh }: {
  overview: Overview; toast: (ok: boolean, m: string) => void; refresh: () => void;
}) {
  const [mode, setMode] = useState("discover");
  const [onlyMissing, setOnlyMissing] = useState(true);
  const [force, setForce] = useState(false);

  const dispatch = overview.system.dispatch_configured;

  async function start() {
    const res = await adminApi.start({ mode, only_missing: onlyMissing, force, dispatch });
    if (!res.ok) throw new Error(res.reason ?? "refused");
    refresh();
    return res;
  }

  return (
    <Card className="p-5 space-y-3">
      <div className="flex items-center gap-2">
        <Play className="w-4 h-4 text-emerald-600" />
        <h2 className="text-sm font-bold text-slate-800">Start a crawl</h2>
        {!dispatch && (
          <span className="text-[11px] text-amber-600 inline-flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> dispatch not configured — run is enqueued for scheduled / Railway workers
          </span>
        )}
      </div>
      <div className="flex flex-wrap items-end gap-4">
        <label className="text-xs text-slate-600">
          <span className="block font-semibold mb-1">Mode</span>
          <select value={mode} onChange={(e) => setMode(e.target.value)}
            className="border border-slate-200 rounded-md px-2 py-1.5 text-sm focus:outline-none">
            <option value="discover">discover</option>
            <option value="monitor">monitor</option>
          </select>
        </label>
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={onlyMissing} onChange={(e) => setOnlyMissing(e.target.checked)} />
          only missing
        </label>
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} />
          force (ignore active run)
        </label>
        <ActionButton label="Start crawl" onAction={start} onResult={toast} />
      </div>

      <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-slate-100">
        <span className="text-xs font-semibold text-slate-500 mr-1">Maintenance:</span>
        <ActionButton label="Clear all stale locks" size="xs" onResult={toast}
          onAction={async () => { await adminApi.clearLocks(); refresh(); }} />
        <ActionButton label="Kill orphaned runs" size="xs" confirm danger onResult={toast}
          onAction={async () => { await adminApi.killOrphans(); refresh(); }} />
      </div>

      <div className="flex flex-wrap gap-3 text-[11px] text-slate-500">
        <span className="inline-flex items-center gap-1"><Lock className="w-3 h-3" /> locks = expired leases</span>
        <span className="inline-flex items-center gap-1"><Unlock className="w-3 h-3" /> reap = requeue + finalize</span>
        <span className="inline-flex items-center gap-1"><Skull className="w-3 h-3" /> orphan = running run, no live worker</span>
      </div>
    </Card>
  );
}
