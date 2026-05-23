"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronRight, RefreshCw } from "lucide-react";
import { adminApi, type RunSummary, type TaskRow } from "@/lib/adminApi";
import {
  ActionButton, Card, ProgressBar, RunStateBadge, TaskStatusBadge,
  fmtDuration, fmtTime, relTime,
} from "./ui";

type Toast = (ok: boolean, msg: string) => void;

function RunControls({ run, toast, refresh }: { run: RunSummary; toast: Toast; refresh: () => void }) {
  const wrap = (fn: () => Promise<unknown>) => async () => { await fn(); refresh(); };
  const live = run.state === "active" || run.state === "stale";
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {run.state === "paused" ? (
        <ActionButton label="Resume" onAction={wrap(() => adminApi.resume(run.id))} onResult={toast} size="xs" />
      ) : live ? (
        <ActionButton label="Pause" onAction={wrap(() => adminApi.pause(run.id))} onResult={toast} size="xs" />
      ) : null}
      {live && (
        <ActionButton label="Stop" onAction={wrap(() => adminApi.stop(run.id))} onResult={toast} confirm size="xs" />
      )}
      <ActionButton label="Reap" onAction={wrap(() => adminApi.reap(run.id))} onResult={toast} size="xs" />
      <ActionButton label="Clear locks" onAction={wrap(() => adminApi.clearLocks(run.id))} onResult={toast} size="xs" />
      <ActionButton label="Retry failed" onAction={wrap(() => adminApi.retryFailed(run.id))} onResult={toast} size="xs" />
      <ActionButton label="Force reset" onAction={wrap(() => adminApi.reset(run.id))} onResult={toast} confirm danger size="xs" />
      <ActionButton label="Cancel" onAction={wrap(() => adminApi.cancel(run.id))} onResult={toast} confirm danger size="xs" />
    </div>
  );
}

function TaskTable({ runId, toast }: { runId: number; toast: Toast }) {
  const [tasks, setTasks] = useState<TaskRow[] | null>(null);
  const [filter, setFilter] = useState<string>("all");
  const [openErr, setOpenErr] = useState<number | null>(null);

  const load = useCallback(
    () => adminApi.tasks(runId).then(setTasks).catch((e) => toast(false, e.message)),
    [runId, toast],
  );
  useEffect(() => { load(); }, [load]);

  if (!tasks) return <div className="p-4 text-sm text-slate-400">Loading tasks…</div>;

  const shown = filter === "all" ? tasks : tasks.filter((t) => t.status === filter);
  const counts = tasks.reduce<Record<string, number>>((a, t) => {
    a[t.status] = (a[t.status] ?? 0) + 1; return a;
  }, {});
  const statuses = ["all", "pending", "running", "done", "failed", "dead", "skipped"];

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5 flex-wrap">
        {statuses.map((s) => (
          <button key={s} onClick={() => setFilter(s)}
            className={`rounded-md px-2 py-0.5 text-[11px] font-semibold ${
              filter === s ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
            {s} {s !== "all" && counts[s] ? `(${counts[s]})` : ""}
          </button>
        ))}
        <button onClick={load} className="ml-auto inline-flex items-center gap-1 text-[11px] text-slate-500 hover:text-slate-800">
          <RefreshCw className="w-3 h-3" /> refresh
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-slate-400 border-b border-slate-200">
            <tr className="text-left">
              <th className="py-1.5 pr-2 font-semibold">Municipality</th>
              <th className="py-1.5 px-2 font-semibold">Status</th>
              <th className="py-1.5 px-2 font-semibold text-right">Pages</th>
              <th className="py-1.5 px-2 font-semibold text-right">Try</th>
              <th className="py-1.5 px-2 font-semibold">Duration</th>
              <th className="py-1.5 px-2 font-semibold">Heartbeat</th>
              <th className="py-1.5 px-2 font-semibold text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((t) => (
              <Fragment key={t.id}>
                <tr className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-1.5 pr-2">
                    <span className="font-medium text-slate-800">{t.municipality_id}</span>
                    {t.name && <span className="text-slate-400"> · {t.name}</span>}
                  </td>
                  <td className="py-1.5 px-2"><TaskStatusBadge status={t.status} lease_expired={t.lease_expired} /></td>
                  <td className="py-1.5 px-2 text-right tabular-nums">{t.pages_found}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums">{t.attempts}/{t.max_attempts}</td>
                  <td className="py-1.5 px-2 text-slate-500">{fmtDuration(t.duration_seconds)}</td>
                  <td className="py-1.5 px-2 text-slate-500">{relTime(t.heartbeat)}</td>
                  <td className="py-1.5 px-2">
                    <div className="flex items-center justify-end gap-1">
                      {t.error && (
                        <button onClick={() => setOpenErr(openErr === t.id ? null : t.id)}
                          className="rounded bg-rose-50 text-rose-600 px-1.5 py-0.5 text-[10px] font-bold">err</button>
                      )}
                      <ActionButton label="Retry" size="xs" onResult={toast}
                        onAction={async () => { await adminApi.retryTask(t.id); await load(); }} />
                      <ActionButton label="Skip" size="xs" onResult={toast}
                        onAction={async () => { await adminApi.skipMuni(runId, t.municipality_id); await load(); }} />
                      <ActionButton label="Re-crawl" size="xs" onResult={toast}
                        onAction={async () => { await adminApi.recrawl(t.municipality_id, t.mode); }} />
                    </div>
                  </td>
                </tr>
                {openErr === t.id && t.error && (
                  <tr className="bg-rose-50/40">
                    <td colSpan={7} className="py-2 px-2">
                      <pre className="whitespace-pre-wrap break-words font-mono text-[11px] text-rose-700">{t.error}</pre>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {shown.length === 0 && (
              <tr><td colSpan={7} className="py-4 text-center text-slate-400">No tasks in this filter</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function RunsPanel({ runs, toast, refresh }: {
  runs: RunSummary[]; toast: Toast; refresh: () => void;
}) {
  const [open, setOpen] = useState<number | null>(null);

  return (
    <Card>
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
        <h2 className="text-sm font-bold text-slate-800">Runs</h2>
        <span className="text-xs text-slate-400">{runs.length} recent</span>
      </div>
      <div className="divide-y divide-slate-100">
        {runs.map((r) => {
          const p = r.progress;
          const isOpen = open === r.id;
          return (
            <div key={r.id}>
              <div className="px-4 py-3 flex flex-col gap-2 lg:flex-row lg:items-center lg:gap-4">
                <button onClick={() => setOpen(isOpen ? null : r.id)}
                  className="flex items-center gap-2 shrink-0 text-left">
                  {isOpen ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
                  <span className="font-bold text-slate-800 text-sm">#{r.id}</span>
                  <RunStateBadge state={r.state} />
                  <span className="text-xs text-slate-400">{r.mode}</span>
                </button>

                <div className="flex-1 min-w-[180px]">
                  <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
                    <span>{p.terminal}/{p.total} · {p.pct}%</span>
                    <span>{p.pages.toLocaleString("es-CR")} pages</span>
                  </div>
                  <ProgressBar pct={p.pct} tone={r.state === "active" ? "emerald" : "blue"} />
                </div>

                <div className="flex items-center gap-3 text-[11px] text-slate-500 shrink-0">
                  <span title="started">{fmtTime(r.started_at)}</span>
                  <span title="duration">{fmtDuration(r.duration_seconds)}</span>
                  {r.pages_per_min != null && <span title="speed">{r.pages_per_min}/min</span>}
                  {r.state === "stale" && <span className="text-amber-600 font-semibold">hb {r.heartbeat_age_min}m</span>}
                </div>
              </div>

              {isOpen && (
                <div className="px-4 pb-4 space-y-3 bg-slate-50/50">
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-500">
                    <span>pending {p.pending}</span><span>running {p.running}</span>
                    <span>done {p.done}</span><span>failed {p.failed}</span>
                    <span>dead {p.dead}</span><span>skipped {p.skipped}</span>
                    {r.worker_id && <span>worker {r.worker_id}</span>}
                  </div>
                  <RunControls run={r} toast={toast} refresh={refresh} />
                  <TaskTable runId={r.id} toast={toast} />
                </div>
              )}
            </div>
          );
        })}
        {runs.length === 0 && <div className="px-4 py-8 text-center text-sm text-slate-400">No runs yet</div>}
      </div>
    </Card>
  );
}
