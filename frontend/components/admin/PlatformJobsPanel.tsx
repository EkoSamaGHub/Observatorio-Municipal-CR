"use client";

import { useCallback, useEffect, useState } from "react";
import {
  RefreshCw, Cpu, CheckCircle, XCircle, Clock, Loader2,
  ChevronRight, ChevronDown, AlertTriangle,
} from "lucide-react";
import {
  adminApi,
  type PlatformJob, type PlatformInfo,
  type PlatformError, type PlatformJobDetail,
} from "@/lib/adminApi";
import { ActionButton, Card, ProgressBar, fmtDuration, fmtTime, relTime } from "./ui";

type Toast = (ok: boolean, msg: string) => void;

function statusColor(status: PlatformJob["status"]): string {
  switch (status) {
    case "RUNNING":   return "text-emerald-600 bg-emerald-50";
    case "QUEUED":    return "text-blue-600 bg-blue-50";
    case "DRAINING":  return "text-amber-600 bg-amber-50";
    case "COMPLETED": return "text-slate-600 bg-slate-100";
    case "FAILED":    return "text-rose-600 bg-rose-50";
    case "CANCELED":  return "text-slate-400 bg-slate-50";
    case "PAUSED":    return "text-amber-600 bg-amber-50";
    default:          return "text-slate-500 bg-slate-100";
  }
}

function StatusIcon({ status }: { status: PlatformJob["status"] }) {
  if (status === "RUNNING" || status === "QUEUED" || status === "DRAINING")
    return <Loader2 className="w-3 h-3 animate-spin" />;
  if (status === "COMPLETED") return <CheckCircle className="w-3 h-3" />;
  if (status === "FAILED")    return <XCircle className="w-3 h-3" />;
  return <Clock className="w-3 h-3" />;
}

function jobPct(job: PlatformJob): number {
  const stats = job.stats;
  if (!stats) return job.status === "COMPLETED" ? 100 : 0;
  const total = stats.pagesDiscovered || 1;
  return Math.min(100, Math.round((stats.pagesExtracted / total) * 100));
}

function jobMunicipalityName(job: PlatformJob): string {
  // Names look like "Observatory Discover [SJ001] (render): Municipalidad de X"
  const m = job.name.match(/:\s*(.+)$/);
  return m ? m[1] : job.name;
}

// A job whose name carries the " (render)" tag is an escalated auto-retry.
function isRenderRetry(job: PlatformJob): boolean {
  return / \(render\):/.test(job.name);
}

function fmtBytes(b: number): string {
  if (b < 1024)        return `${b} B`;
  if (b < 1024 ** 2)   return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 ** 3)   return `${(b / 1024 ** 2).toFixed(1)} MB`;
  return `${(b / 1024 ** 3).toFixed(2)} GB`;
}

const STAGE_STYLE: Record<string, string> = {
  fetch:   "bg-blue-50 text-blue-700",
  render:  "bg-violet-50 text-violet-700",
  extract: "bg-amber-50 text-amber-700",
  embed:   "bg-emerald-50 text-emerald-700",
};

// Human explanations for the platform's terminal error codes.
function explainCode(code: string): string | null {
  if (code.startsWith("SSRF:")) return "Blocked by SSRF guard (DNS did not resolve or pointed to a private/reserved IP).";
  switch (code) {
    case "RETRY_EXHAUSTED": return "All fetch attempts failed (timeout, connection reset, or repeated 5xx).";
    case "TOO_LARGE":       return "Response exceeded the max page size and was skipped.";
    case "BAD_CONTENT_TYPE":return "Content type not in the allowed list for this crawl.";
    case "ROBOTS_BLOCKED":  return "Disallowed by the site's robots.txt.";
    case "HTTP_4XX":        return "Server returned a client error (e.g. 403 / 404).";
    case "HTTP_5XX":        return "Server returned a server error (5xx).";
    default:                return null;
  }
}

function TaskStatusBreakdown({ tasks }: { tasks: Record<string, number> }) {
  const order = ["DONE", "EXTRACTED", "RENDERED", "IN_PROGRESS", "PENDING", "ERRORED", "SKIPPED"];
  const entries = order.filter((k) => tasks[k]).map((k) => [k, tasks[k]] as const);
  const tone: Record<string, string> = {
    DONE: "text-emerald-600", EXTRACTED: "text-emerald-600", RENDERED: "text-blue-600",
    IN_PROGRESS: "text-blue-600", PENDING: "text-slate-500",
    ERRORED: "text-rose-600", SKIPPED: "text-amber-600",
  };
  if (entries.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px]">
      {entries.map(([k, v]) => (
        <span key={k} className={tone[k] ?? "text-slate-500"}>
          {k.toLowerCase().replace("_", " ")} {v}
        </span>
      ))}
    </div>
  );
}

function ErrorList({ jobId, toast, isRetry }: { jobId: string; toast: Toast; isRetry: boolean }) {
  const [detail, setDetail] = useState<PlatformJobDetail | null>(null);
  const [errors, setErrors] = useState<PlatformError[] | null>(null);
  const [byCode, setByCode] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    Promise.all([
      adminApi.platformJobDetail(jobId).catch(() => null),
      adminApi.platformJobErrors(jobId, 100).catch(() => null),
    ])
      .then(([d, e]) => {
        if (!alive) return;
        setDetail(d);
        setErrors(e?.errors ?? []);
        setByCode(e?.by_code ?? {});
      })
      .catch((err) => toast(false, (err as Error).message))
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [jobId, toast]);

  if (loading) {
    return (
      <div className="px-3 py-3 text-[11px] text-slate-400 inline-flex items-center gap-1.5">
        <Loader2 className="w-3 h-3 animate-spin" /> loading details…
      </div>
    );
  }

  const tasks = detail?.tasksByStatus ?? {};
  const stats = detail?.stats;
  const errored = tasks.ERRORED ?? 0;
  const extracted = stats?.pagesExtracted ?? 0;
  // "Empty success": completed with little/no content and no recorded errors —
  // usually a WAF/JS-only site that returned a stub. Surface it explicitly.
  const emptySuccess =
    (errors?.length ?? 0) === 0 && errored === 0 && extracted <= 1;

  return (
    <div className="bg-slate-50/70 border-t border-slate-100 px-3 py-3 space-y-3">
      {/* task breakdown */}
      {Object.keys(tasks).length > 0 && (
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400 mb-1">Tasks</p>
          <TaskStatusBreakdown tasks={tasks} />
        </div>
      )}

      {emptySuccess && (
        <div className="flex items-start gap-2 rounded-md bg-amber-50 border border-amber-200 px-3 py-2 text-[11px] text-amber-800">
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          {isRetry ? (
            <span>
              Re-ran with full rendering and still extracted {extracted} page{extracted === 1 ? "" : "s"} —
              the site sits behind an anti-bot WAF (e.g. Cloudflare “Just a moment”) that headless
              rendering can’t clear. This municipality needs a <b>bot-bypass proxy</b> (set
              <code className="mx-0.5">ZENROWS_API_KEY</code> or top up
              <code className="mx-0.5">SCRAPINGBEE_API_KEY</code> on the platform).
            </span>
          ) : (
            <span>
              Completed but extracted {extracted} page{extracted === 1 ? "" : "s"} with no errors —
              likely a JS-only shell or WAF stub. It will be <b>re-run automatically with full
              rendering</b>; watch for a “(render)” retry job appearing above.
            </span>
          )}
        </div>
      )}

      {/* error summary by code */}
      {Object.keys(byCode).length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(byCode).map(([code, n]) => (
            <span key={code} className="inline-flex items-center gap-1 rounded-md bg-rose-50 text-rose-700 px-1.5 py-0.5 text-[10px] font-semibold">
              {code} ×{n}
            </span>
          ))}
        </div>
      )}

      {/* error rows */}
      {errors && errors.length > 0 ? (
        <div className="space-y-1.5 max-h-72 overflow-y-auto">
          {errors.map((e) => {
            const why = explainCode(e.code);
            return (
              <div key={e.id} className="rounded-md bg-white border border-slate-200 px-2.5 py-1.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${STAGE_STYLE[e.stage] ?? "bg-slate-100 text-slate-600"}`}>
                    {e.stage}
                  </span>
                  <span className="font-mono text-[11px] font-semibold text-rose-700">{e.code}</span>
                  {e.terminal && (
                    <span className="text-[9px] uppercase font-bold text-rose-400">terminal</span>
                  )}
                  <span className="ml-auto text-[10px] text-slate-400">{fmtTime(e.occurredAt)}</span>
                </div>
                {e.message && (
                  <p className="mt-0.5 font-mono text-[11px] text-slate-600 break-all">{e.message}</p>
                )}
                {why && <p className="mt-0.5 text-[10px] text-slate-400">{why}</p>}
              </div>
            );
          })}
        </div>
      ) : !emptySuccess ? (
        <p className="text-[11px] text-slate-400">No recorded errors for this job.</p>
      ) : null}
    </div>
  );
}

function JobRow({ job, toast, onCancel, open, onToggle }: {
  job: PlatformJob;
  toast: Toast;
  onCancel: () => void;
  open: boolean;
  onToggle: () => void;
}) {
  const live = job.status === "RUNNING" || job.status === "QUEUED" || job.status === "DRAINING";
  const pct = jobPct(job);
  const durationMs = job.startedAt && job.completedAt
    ? new Date(job.completedAt).getTime() - new Date(job.startedAt).getTime()
    : job.startedAt
    ? Date.now() - new Date(job.startedAt).getTime()
    : null;

  const errCount = job.stats?.errors ?? job.errorCount ?? 0;
  const retry = isRenderRetry(job);

  return (
    <div className="border-b border-slate-100 last:border-0">
      <div className="py-2.5">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <button onClick={onToggle} className="flex items-center gap-2 min-w-0 text-left">
            {open ? <ChevronDown className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  : <ChevronRight className="w-3.5 h-3.5 text-slate-400 shrink-0" />}
            <span className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-bold ${statusColor(job.status)}`}>
              <StatusIcon status={job.status} />
              {job.status}
            </span>
            <span className="text-xs font-semibold text-slate-700 truncate">
              {jobMunicipalityName(job)}
            </span>
            {retry && (
              <span className="rounded bg-violet-100 text-violet-700 px-1.5 py-0.5 text-[9px] font-bold uppercase">
                render retry
              </span>
            )}
            {errCount > 0 && (
              <span className="inline-flex items-center gap-0.5 rounded bg-rose-50 text-rose-600 px-1.5 py-0.5 text-[10px] font-bold">
                <AlertTriangle className="w-2.5 h-2.5" /> {errCount}
              </span>
            )}
          </button>
          <div className="flex items-center gap-3 text-[11px] text-slate-400 shrink-0">
            {durationMs !== null && (
              <span>{fmtDuration(Math.round(durationMs / 1000))}</span>
            )}
            <span>{relTime(job.createdAt)}</span>
            {live && (
              <ActionButton
                label="Cancel"
                size="xs"
                confirm
                danger
                onResult={toast}
                onAction={async () => { await adminApi.cancelPlatformJob(job.id); onCancel(); }}
              />
            )}
          </div>
        </div>
        <div className="mt-1.5 ml-5 flex items-center gap-3 text-[11px] text-slate-500">
          {job.stats ? (
            <>
              <span>{job.stats.pagesExtracted.toLocaleString("es-CR")} extracted</span>
              <span>{job.stats.pagesFetched.toLocaleString("es-CR")} fetched</span>
              {job.stats.bytesFetched > 0 && <span>{fmtBytes(job.stats.bytesFetched)}</span>}
            </>
          ) : (
            <>
              {(job.pagesFetched ?? 0) > 0 && <span>{(job.pagesFetched ?? 0).toLocaleString("es-CR")} fetched</span>}
            </>
          )}
          <span className="font-mono text-[10px] text-slate-300">{job.id}</span>
        </div>
        {live && (
          <div className="mt-1.5 ml-5">
            <ProgressBar pct={pct} tone="emerald" />
          </div>
        )}
      </div>
      {open && <ErrorList jobId={job.id} toast={toast} isRetry={retry} />}
    </div>
  );
}

export default function PlatformJobsPanel({
  platform,
  toast,
  refresh,
}: {
  platform: PlatformInfo | undefined;
  toast: Toast;
  refresh: () => void;
}) {
  const [jobs, setJobs] = useState<PlatformJob[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    adminApi
      .platformJobs(30)
      .then(setJobs)
      .catch((e) => toast(false, e.message))
      .finally(() => setLoading(false));
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  const platformOk = platform?.ok ?? true;
  const platformUrl = platform?.url ?? "";

  return (
    <Card className="p-5 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-violet-600" />
          <h2 className="text-sm font-bold text-slate-800">Crawler platform jobs</h2>
          {!platformOk && (
            <span className="text-[11px] text-rose-500 font-semibold">
              unreachable ({platformUrl})
            </span>
          )}
          {platformOk && platformUrl && (
            <span className="text-[11px] text-slate-400">{platformUrl}</span>
          )}
        </div>
        <button
          onClick={load}
          className="inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-700"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
          refresh
        </button>
      </div>

      {jobs === null ? (
        <p className="text-sm text-slate-400">Loading jobs…</p>
      ) : jobs.length === 0 ? (
        <p className="text-sm text-slate-400">No platform jobs yet. Start a crawl above.</p>
      ) : (
        <>
          <div className="divide-y divide-slate-100">
            {jobs.map((j) => (
              <JobRow
                key={j.id}
                job={j}
                toast={toast}
                onCancel={() => { load(); refresh(); }}
                open={openId === j.id}
                onToggle={() => setOpenId(openId === j.id ? null : j.id)}
              />
            ))}
          </div>
          <p className="text-[11px] text-slate-400 pt-1">Click a job to see its error log and task breakdown.</p>
        </>
      )}
    </Card>
  );
}
