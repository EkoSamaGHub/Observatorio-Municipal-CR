"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import type { RunState } from "@/lib/adminApi";

// ── formatting helpers ────────────────────────────────────────────────────

export function fmtDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  const s = Math.floor(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${sec}s`;
  return `${sec}s`;
}

export function relTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (!isFinite(diff)) return "—";
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-CR");
}

// ── badges ────────────────────────────────────────────────────────────────

const RUN_STATE_STYLE: Record<RunState, { dot: string; bg: string; text: string }> = {
  active:    { dot: "bg-emerald-500", bg: "bg-emerald-50",  text: "text-emerald-700" },
  stale:     { dot: "bg-amber-500",   bg: "bg-amber-50",    text: "text-amber-700" },
  orphaned:  { dot: "bg-orange-500",  bg: "bg-orange-50",   text: "text-orange-700" },
  paused:    { dot: "bg-sky-500",     bg: "bg-sky-50",      text: "text-sky-700" },
  stopped:   { dot: "bg-slate-500",   bg: "bg-slate-100",   text: "text-slate-700" },
  cancelled: { dot: "bg-rose-500",    bg: "bg-rose-50",     text: "text-rose-700" },
  done:      { dot: "bg-blue-500",    bg: "bg-blue-50",     text: "text-blue-700" },
};

export function RunStateBadge({ state }: { state: RunState }) {
  const s = RUN_STATE_STYLE[state] ?? RUN_STATE_STYLE.done;
  const pulse = state === "active";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${s.bg} ${s.text}`}>
      <span className="relative flex h-2 w-2">
        {pulse && <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${s.dot} opacity-60`} />}
        <span className={`relative inline-flex rounded-full h-2 w-2 ${s.dot}`} />
      </span>
      {state}
    </span>
  );
}

const TASK_STATUS_STYLE: Record<string, string> = {
  pending:   "bg-slate-100 text-slate-600",
  running:   "bg-emerald-50 text-emerald-700",
  done:      "bg-blue-50 text-blue-700",
  failed:    "bg-amber-50 text-amber-700",
  dead:      "bg-rose-50 text-rose-700",
  skipped:   "bg-violet-50 text-violet-700",
};

export function TaskStatusBadge({ status, lease_expired }: { status: string; lease_expired?: boolean }) {
  const cls = TASK_STATUS_STYLE[status] ?? "bg-slate-100 text-slate-600";
  return (
    <span className="inline-flex items-center gap-1">
      <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${cls}`}>{status}</span>
      {lease_expired && (
        <span className="rounded-full bg-orange-100 text-orange-700 px-1.5 py-0.5 text-[10px] font-bold uppercase">
          stale lock
        </span>
      )}
    </span>
  );
}

// ── layout primitives ──────────────────────────────────────────────────────

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white border border-slate-200 rounded-xl shadow-sm ${className}`}>
      {children}
    </div>
  );
}

export function Stat({ label, value, sub, tone = "slate" }: {
  label: string; value: React.ReactNode; sub?: string;
  tone?: "slate" | "blue" | "emerald" | "amber" | "rose";
}) {
  const tones: Record<string, string> = {
    slate: "text-slate-800", blue: "text-blue-700", emerald: "text-emerald-700",
    amber: "text-amber-600", rose: "text-rose-600",
  };
  return (
    <Card className="px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`text-2xl font-black leading-tight mt-0.5 ${tones[tone]}`}>{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
    </Card>
  );
}

export function ProgressBar({ pct, tone = "blue" }: { pct: number; tone?: "blue" | "emerald" }) {
  const grad = tone === "blue" ? "from-blue-500 to-blue-400" : "from-emerald-500 to-emerald-400";
  return (
    <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
      <div
        className={`h-2.5 rounded-full bg-gradient-to-r ${grad} transition-all duration-700`}
        style={{ width: `${Math.min(Math.max(pct, 0), 100)}%` }}
      />
    </div>
  );
}

// ── action button with optional confirm + inline loading/error ──────────────

export function ActionButton({
  label, onAction, onResult, confirm = false, danger = false, disabled = false, size = "sm",
}: {
  label: string;
  onAction: () => Promise<unknown>;
  onResult?: (ok: boolean, msg: string) => void;
  confirm?: boolean;
  danger?: boolean;
  disabled?: boolean;
  size?: "sm" | "xs";
}) {
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);

  const base = danger
    ? "bg-rose-50 text-rose-700 hover:bg-rose-100 border-rose-200"
    : "bg-slate-50 text-slate-700 hover:bg-slate-100 border-slate-200";
  const pad = size === "xs" ? "px-2 py-1 text-[11px]" : "px-3 py-1.5 text-xs";

  async function run() {
    setBusy(true);
    try {
      await onAction();
      onResult?.(true, `${label}: ok`);
    } catch (e) {
      onResult?.(false, `${label}: ${(e as Error).message}`);
    } finally {
      setBusy(false);
      setArmed(false);
    }
  }

  if (confirm && armed) {
    return (
      <span className="inline-flex items-center gap-1">
        <button onClick={run} disabled={busy}
          className="rounded-md bg-rose-600 text-white px-2 py-1 text-[11px] font-semibold hover:bg-rose-700 disabled:opacity-50">
          {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : "Confirm"}
        </button>
        <button onClick={() => setArmed(false)} disabled={busy}
          className="rounded-md bg-slate-100 text-slate-600 px-2 py-1 text-[11px] font-semibold hover:bg-slate-200">
          Cancel
        </button>
      </span>
    );
  }

  return (
    <button
      onClick={() => (confirm ? setArmed(true) : run())}
      disabled={disabled || busy}
      className={`inline-flex items-center gap-1 rounded-md border font-semibold transition-colors disabled:opacity-40 ${pad} ${base}`}
    >
      {busy && <Loader2 className="w-3 h-3 animate-spin" />}
      {label}
    </button>
  );
}
