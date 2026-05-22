"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Stats {
  total_runs: number;
  completed_hours: number;
  first_run_at: string | null;
  total_pages: number;
  total_docs: number;
  active_started_at: string | null;
  dev_hours: number;
  dev_sessions: number;
}

async function fetchStats(): Promise<Stats | null> {
  try {
    const res = await fetch(`${API_BASE}/runs/stats`, { cache: "no-store" });
    return res.json();
  } catch {
    return null;
  }
}

function fmt(n: number, decimals = 0): string {
  return n.toLocaleString("es-CR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function sinceDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("es-CR", { day: "numeric", month: "short", year: "numeric" });
}

export default function EffortCounter() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [totalHours, setTotalHours] = useState(0);

  // Fetch stats on mount and every 30s
  useEffect(() => {
    fetchStats().then(setStats);
    const id = setInterval(() => fetchStats().then(setStats), 30_000);
    return () => clearInterval(id);
  }, []);

  // Tick every second: completed runs + elapsed time of active run
  useEffect(() => {
    if (!stats) return;

    const tick = () => {
      let hours = stats.completed_hours;
      if (stats.active_started_at) {
        const elapsedMs = Date.now() - new Date(stats.active_started_at).getTime();
        hours += elapsedMs / 1000 / 3600;
      }
      setTotalHours(hours);
    };

    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [stats]);

  if (!stats || stats.dev_hours === undefined) return null;

  const machineHrs  = Math.floor(totalHours);
  const machineMins = Math.floor((totalHours - machineHrs) * 60);
  const machineSecs = Math.floor(((totalHours - machineHrs) * 60 - machineMins) * 60);

  const devHours    = stats.dev_hours ?? 0;
  const devSessions = stats.dev_sessions ?? 0;
  const totalInvestment = totalHours + devHours;

  return (
    <div className="relative bg-gradient-to-br from-violet-600 to-purple-700 rounded-xl text-white overflow-hidden shadow-lg">
      <div className="absolute inset-0 opacity-10 pointer-events-none">
        <div className="absolute -top-8 -right-8 w-48 h-48 rounded-full bg-white" />
        <div className="absolute -bottom-12 -left-8 w-56 h-56 rounded-full bg-white" />
      </div>

      <div className="relative px-6 py-5 space-y-4">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-purple-200" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
            <span className="text-sm font-semibold text-purple-100">Inversión total en el proyecto</span>
          </div>
          {stats.active_started_at && (
            <span className="flex items-center gap-1.5 text-xs bg-white/15 rounded-full px-2.5 py-1 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-green-300 animate-pulse" />
              Corriendo
            </span>
          )}
        </div>

        {/* Two tracks: human + machine */}
        <div className="grid grid-cols-2 gap-3">

          {/* Human hours */}
          <div className="bg-white/10 rounded-xl p-4 space-y-1">
            <div className="flex items-center gap-1.5 text-xs text-purple-200 mb-2">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
              </svg>
              Tú — desarrollo
            </div>
            <div className="text-3xl font-bold tabular-nums">
              {fmt(devHours, 1)}<span className="text-lg text-purple-300 ml-1">h</span>
            </div>
            <div className="text-xs text-purple-300">
              {devSessions} {devSessions === 1 ? "sesión" : "sesiones"} registradas
            </div>
            {stats.dev_hours === 0 && (
              <div className="text-xs text-purple-300 italic mt-1">
                Registra tus horas →<br />
                <code className="text-purple-200 not-italic">python log_hours.py</code>
              </div>
            )}
          </div>

          {/* Machine hours */}
          <div className="bg-white/10 rounded-xl p-4 space-y-1">
            <div className="flex items-center gap-1.5 text-xs text-purple-200 mb-2">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 17.25v1.007a3 3 0 0 1-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0 1 15 18.257V17.25m6-12V15a2.25 2.25 0 0 1-2.25 2.25H5.25A2.25 2.25 0 0 1 3 15V5.25m18 0A2.25 2.25 0 0 0 18.75 3H5.25A2.25 2.25 0 0 0 3 5.25m18 0H3" />
              </svg>
              Máquina — rastreo
            </div>
            <div className="text-3xl font-bold tabular-nums">
              {String(machineHrs).padStart(2, "0")}
              <span className="text-lg text-purple-300">h </span>
              {String(machineMins).padStart(2, "0")}
              <span className="text-lg text-purple-300">m </span>
              {String(machineSecs).padStart(2, "0")}
              <span className="text-lg text-purple-300">s</span>
            </div>
            <div className="text-xs text-purple-300">
              {fmt(stats.total_runs)} {stats.total_runs === 1 ? "run" : "runs"} · {fmt(stats.total_pages)} páginas
            </div>
          </div>
        </div>

        {/* Combined total */}
        <div className="bg-white/15 rounded-lg px-4 py-3 flex items-center justify-between">
          <span className="text-sm text-purple-100 font-medium">Total invertido</span>
          <span className="text-xl font-bold tabular-nums">
            {fmt(totalInvestment, 1)}<span className="text-sm text-purple-300 ml-1">horas</span>
          </span>
        </div>

        {/* Footer */}
        <div className="text-xs text-purple-300 flex items-center justify-between pt-1">
          <span>{stats.first_run_at ? `Desde ${sinceDate(stats.first_run_at)}` : "Sin datos aún"}</span>
          <span>{fmt(stats.total_docs)} documentos indexados</span>
        </div>

      </div>
    </div>
  );
}
