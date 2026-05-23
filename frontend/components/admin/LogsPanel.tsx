"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Search } from "lucide-react";
import { adminApi, type LogEvent } from "@/lib/adminApi";
import { Card, fmtTime } from "./ui";

const LEVEL_STYLE: Record<string, string> = {
  info: "text-slate-500",
  warn: "text-amber-600",
  error: "text-rose-600",
};

export default function LogsPanel({ toast, auto }: { toast: (ok: boolean, m: string) => void; auto: boolean }) {
  const [logs, setLogs] = useState<LogEvent[]>([]);
  const [search, setSearch] = useState("");
  const [level, setLevel] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);

  const load = useCallback(() => {
    adminApi.logs({ search, level, limit: 200 })
      .then(setLogs)
      .catch((e) => toast(false, e.message));
  }, [search, level, toast]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!auto) return;
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [auto, load]);

  return (
    <Card>
      <div className="px-4 py-3 border-b border-slate-100 flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-bold text-slate-800 mr-auto">Event log</h2>
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="search…"
            className="pl-7 pr-2 py-1 text-xs border border-slate-200 rounded-md w-40 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
        </div>
        <select value={level} onChange={(e) => setLevel(e.target.value)}
          className="text-xs border border-slate-200 rounded-md px-2 py-1 focus:outline-none">
          <option value="">all levels</option>
          <option value="info">info</option>
          <option value="warn">warn</option>
          <option value="error">error</option>
        </select>
        <button onClick={load} className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800">
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>
      <div className="max-h-[460px] overflow-y-auto divide-y divide-slate-50 font-mono text-[11px]">
        {logs.map((l) => (
          <div key={l.id} className="px-4 py-1.5 hover:bg-slate-50">
            <button onClick={() => setExpanded(expanded === l.id ? null : l.id)}
              className="w-full flex items-start gap-2 text-left">
              <span className="text-slate-400 shrink-0 w-[120px]">{fmtTime(l.created_at)}</span>
              <span className={`shrink-0 w-12 font-bold uppercase ${LEVEL_STYLE[l.level] ?? "text-slate-500"}`}>{l.level}</span>
              <span className="shrink-0 w-32 text-blue-700 font-semibold truncate">{l.event}</span>
              <span className="text-slate-600 truncate flex-1">{l.message ?? ""}</span>
              {l.run_id != null && <span className="text-slate-300 shrink-0">#{l.run_id}</span>}
            </button>
            {expanded === l.id && l.meta && (
              <pre className="mt-1 ml-[120px] whitespace-pre-wrap break-words text-slate-500 bg-slate-50 rounded p-2">
                {JSON.stringify(l.meta, null, 2)}
              </pre>
            )}
          </div>
        ))}
        {logs.length === 0 && <div className="px-4 py-8 text-center text-slate-400 font-sans">No events</div>}
      </div>
    </Card>
  );
}
