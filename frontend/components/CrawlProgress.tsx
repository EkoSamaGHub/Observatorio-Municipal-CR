"use client";

import { useEffect, useState } from "react";
import type { ActiveRun } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchActive(): Promise<ActiveRun> {
  try {
    const res = await fetch(`${API_BASE}/runs/active`, { cache: "no-store" });
    return res.json();
  } catch {
    return { active: false };
  }
}

function ProgressBar({
  pct,
  color,
}: {
  pct: number;
  color: "blue" | "emerald";
}) {
  const from = color === "blue" ? "from-blue-500" : "from-emerald-500";
  const to = color === "blue" ? "to-blue-400" : "to-emerald-400";
  return (
    <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
      <div
        className={`h-2.5 rounded-full bg-gradient-to-r ${from} ${to} transition-all duration-700`}
        style={{ width: `${Math.max(pct, 1)}%` }}
      />
    </div>
  );
}

export default function CrawlProgress() {
  const [data, setData] = useState<ActiveRun | null>(null);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    fetchActive().then(setData);
    const poll = setInterval(() => fetchActive().then(setData), 6000);
    return () => clearInterval(poll);
  }, []);

  useEffect(() => {
    if (!data?.active || !data.started_at) return;
    const tick = setInterval(() => {
      setElapsed(Math.floor((Date.now() - new Date(data.started_at!).getTime()) / 1000));
    }, 1000);
    return () => clearInterval(tick);
  }, [data?.active, data?.started_at]);

  if (!data) return null;

  if (!data.active) {
    return (
      <div className="flex items-center gap-2 text-xs text-slate-500 bg-slate-100 rounded-lg px-4 py-2.5">
        <span className="w-2 h-2 rounded-full bg-slate-400 shrink-0" />
        Sin rastreo activo en este momento
      </div>
    );
  }

  const TOTAL_MUNICIPALITIES = 84;
  const total = TOTAL_MUNICIPALITIES;
  const done = Math.min(data.municipalities_done ?? 0, total);
  const withData = Math.min(data.municipalities_with_data ?? 0, total);
  const pages = data.pages_crawled ?? 0;

  const historicalPct = Math.min(100, Math.round((withData / total) * 100));
  const sessionPct = Math.min(100, Math.round((done / total) * 100));

  const hrs = Math.floor(elapsed / 3600);
  const mins = Math.floor((elapsed % 3600) / 60);
  const secs = elapsed % 60;
  const elapsedStr = hrs > 0
    ? `${hrs}h ${mins}m`
    : mins > 0
    ? `${mins}m ${secs}s`
    : `${secs}s`;

  return (
    <div className="bg-white border border-blue-200 rounded-xl overflow-hidden shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-blue-100 bg-blue-50">
        <div className="flex items-center gap-2.5">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-blue-500" />
          </span>
          <span className="text-sm font-semibold text-blue-900">Rastreo en progreso</span>
        </div>
        <div className="flex items-center gap-4 text-xs text-blue-700 font-medium">
          <span>{pages.toLocaleString("es-CR")} páginas esta sesión</span>
          <span className="text-blue-300">·</span>
          <span>{elapsedStr} transcurridos</span>
        </div>
      </div>

      <div className="px-5 py-4 space-y-4">
        {/* Historical coverage bar */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium text-slate-700">Cobertura histórica</span>
            <span className="text-slate-500">
              {withData} / {total} municipalidades &nbsp;·&nbsp; {historicalPct}%
            </span>
          </div>
          <ProgressBar pct={historicalPct} color="emerald" />
        </div>

        {/* Current run bar */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium text-slate-700">Esta sesión</span>
            <span className="text-slate-500">
              {done} / {total} municipalidades &nbsp;·&nbsp; {sessionPct}%
            </span>
          </div>
          <ProgressBar pct={sessionPct} color="blue" />
        </div>

        {/* Current URL */}
        {data.current_municipality && (
          <div className="flex items-center gap-2 text-xs text-slate-500 pt-1">
            <span className="font-medium text-slate-700 shrink-0">
              Ahora: {data.current_municipality}
            </span>
            {data.current_url && (
              <>
                <span className="text-slate-300">·</span>
                <span className="truncate font-mono text-slate-400">{data.current_url}</span>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
