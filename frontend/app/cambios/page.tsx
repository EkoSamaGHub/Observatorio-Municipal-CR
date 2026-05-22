import { getTranslations } from "next-intl/server";
import { api } from "@/lib/api";
import Link from "next/link";
import { GitCompareArrows, ExternalLink, Building2 } from "lucide-react";

export default async function CambiosPage() {
  const t = await getTranslations("cambios");

  let allDiffs: Array<{
    id: number; municipality_id: string; url: string;
    old_hash: string | null; new_hash: string | null; detected_at: string;
  }> = [];

  let muniNames: Record<string, string> = {};

  try {
    const municipalities = await api.getMunicipalities();
    muniNames = Object.fromEntries(municipalities.map((m) => [m.id, m.name]));
    const crawled = municipalities.filter((m) => m.changes_detected > 0);
    const diffsPerMuni = await Promise.all(crawled.map((m) => api.getMunicipalityDiffs(m.id, 20)));
    allDiffs = diffsPerMuni
      .flat()
      .sort((a, b) => new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime());
  } catch {
    // API not reachable
  }

  const groupByDate = (diffs: typeof allDiffs) => {
    const groups: Record<string, typeof allDiffs> = {};
    for (const d of diffs) {
      const date = new Date(d.detected_at).toLocaleDateString("es-CR", {
        weekday: "long", year: "numeric", month: "long", day: "numeric",
      });
      if (!groups[date]) groups[date] = [];
      groups[date].push(d);
    }
    return Object.entries(groups);
  };

  const grouped = groupByDate(allDiffs);

  return (
    <div className="space-y-6">

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{t("titulo")}</h1>
          <p className="text-slate-500 text-sm mt-1">{t("subtitulo")}</p>
        </div>
        {allDiffs.length > 0 && (
          <div className="shrink-0 bg-orange-50 border border-orange-200 text-orange-700 text-xs font-bold px-3 py-1.5 rounded-full flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
            {allDiffs.length} cambios
          </div>
        )}
      </div>

      {grouped.length > 0 ? (
        <div className="space-y-6">
          {grouped.map(([date, diffs]) => (
            <div key={date}>
              <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3 capitalize">{date}</p>
              <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm divide-y divide-slate-50">
                {diffs.map((d) => {
                  const muniName = muniNames[d.municipality_id] ?? d.municipality_id;
                  const shortUrl = d.url.replace(/^https?:\/\/[^/]+/, "").replace(/\/$/, "") || "/";
                  return (
                    <div key={d.id} className="px-5 py-4 flex items-start gap-4 hover:bg-slate-50/60 transition-colors">
                      {/* Timeline dot */}
                      <div className="flex flex-col items-center pt-1 shrink-0">
                        <div className="w-2 h-2 rounded-full bg-orange-400 ring-2 ring-orange-100" />
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <Link
                            href={`/municipalidades/${d.municipality_id}`}
                            className="flex items-center gap-1 text-xs font-semibold text-slate-600 hover:text-blue-600 transition-colors"
                          >
                            <Building2 className="w-3 h-3" />
                            {muniName}
                          </Link>
                          <span className="text-slate-200">·</span>
                          <span className="text-xs text-slate-400">
                            {new Date(d.detected_at).toLocaleTimeString("es-CR", { hour: "2-digit", minute: "2-digit" })}
                          </span>
                        </div>
                        <a
                          href={d.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="group flex items-center gap-1.5 text-sm font-medium text-blue-700 hover:underline"
                        >
                          <span className="truncate">{shortUrl}</span>
                          <ExternalLink className="w-3 h-3 text-slate-400 group-hover:text-blue-500 shrink-0 transition-colors" />
                        </a>
                        {d.old_hash && d.new_hash && (
                          <div className="flex items-center gap-2 mt-1.5">
                            <span className="text-xs font-mono bg-red-50 text-red-600 border border-red-100 px-1.5 py-0.5 rounded">
                              {d.old_hash.slice(0, 8)}
                            </span>
                            <GitCompareArrows className="w-3 h-3 text-slate-300" />
                            <span className="text-xs font-mono bg-emerald-50 text-emerald-600 border border-emerald-100 px-1.5 py-0.5 rounded">
                              {d.new_hash.slice(0, 8)}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-2xl text-center py-20 space-y-3">
          <GitCompareArrows className="w-10 h-10 text-slate-200 mx-auto" />
          <p className="text-slate-400 text-sm font-medium">{t("sin_cambios")}</p>
        </div>
      )}
    </div>
  );
}
