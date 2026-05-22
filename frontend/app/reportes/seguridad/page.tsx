import { getTranslations } from "next-intl/server";
import { api, DomainExpiry, SSLReport } from "@/lib/api";
import { Shield, Globe, AlertTriangle, CheckCircle2, XCircle, CalendarDays } from "lucide-react";

const GRADE_CONFIG: Record<string, { bg: string; text: string; ring: string }> = {
  "A+": { bg: "bg-emerald-500", text: "text-white",      ring: "ring-emerald-200" },
  "A":  { bg: "bg-emerald-400", text: "text-white",      ring: "ring-emerald-200" },
  "B":  { bg: "bg-yellow-400",  text: "text-yellow-900", ring: "ring-yellow-200" },
  "C":  { bg: "bg-orange-400",  text: "text-white",      ring: "ring-orange-200" },
  "D":  { bg: "bg-orange-500",  text: "text-white",      ring: "ring-orange-200" },
  "F":  { bg: "bg-red-500",     text: "text-white",      ring: "ring-red-200" },
  "T":  { bg: "bg-red-600",     text: "text-white",      ring: "ring-red-200" },
  "M":  { bg: "bg-red-700",     text: "text-white",      ring: "ring-red-200" },
};

function GradeCircle({ grade }: { grade: string | null }) {
  if (!grade) {
    return (
      <div className="w-10 h-10 rounded-full bg-slate-100 border-2 border-slate-200 flex items-center justify-center">
        <span className="text-xs font-bold text-slate-400">—</span>
      </div>
    );
  }
  const cfg = GRADE_CONFIG[grade] ?? { bg: "bg-slate-400", text: "text-white", ring: "ring-slate-200" };
  return (
    <div className={`w-10 h-10 rounded-full ${cfg.bg} ring-2 ${cfg.ring} flex items-center justify-center shadow-sm`}>
      <span className={`text-xs font-black ${cfg.text}`}>{grade}</span>
    </div>
  );
}

function ExpiryBadge({ dateStr }: { dateStr: string | null }) {
  if (!dateStr) return <span className="text-slate-300 text-xs">—</span>;
  const date  = new Date(dateStr);
  const daysLeft = Math.floor((date.getTime() - Date.now()) / 86_400_000);
  const label = date.toLocaleDateString("es-CR");

  if (daysLeft < 0) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-red-700 bg-red-50 border border-red-200 rounded-full px-2 py-0.5">
        <XCircle className="w-3 h-3" /> Expirado
      </span>
    );
  }
  if (daysLeft < 30) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-red-600 bg-red-50 border border-red-200 rounded-full px-2 py-0.5">
        <AlertTriangle className="w-3 h-3" /> {label} ({daysLeft}d)
      </span>
    );
  }
  if (daysLeft < 90) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-orange-600 bg-orange-50 border border-orange-200 rounded-full px-2 py-0.5">
        <CalendarDays className="w-3 h-3" /> {label} ({daysLeft}d)
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full px-2 py-0.5">
      <CheckCircle2 className="w-3 h-3" /> {label}
    </span>
  );
}

interface MergedRow {
  municipality_id: string;
  municipality_name: string;
  province: string;
  domain: string;
  ssl: SSLReport | null;
  domain_rec: DomainExpiry | null;
}

export default async function SeguridadPage() {
  const t = await getTranslations("reportes");

  let sslReports: SSLReport[] = [];
  let domainExpiry: DomainExpiry[] = [];
  try {
    [sslReports, domainExpiry] = await Promise.all([
      api.getSSLReports(),
      api.getDomainExpiry(),
    ]);
  } catch {
    // API not reachable
  }

  const map = new Map<string, MergedRow>();
  for (const s of sslReports) {
    map.set(s.municipality_id, { municipality_id: s.municipality_id, municipality_name: s.municipality_name, province: s.province, domain: s.domain, ssl: s, domain_rec: null });
  }
  for (const d of domainExpiry) {
    const ex = map.get(d.municipality_id);
    if (ex) ex.domain_rec = d;
    else map.set(d.municipality_id, { municipality_id: d.municipality_id, municipality_name: d.municipality_name, province: d.province, domain: d.domain, ssl: null, domain_rec: d });
  }

  const rows = Array.from(map.values()).sort(
    (a, b) => a.province.localeCompare(b.province, "es") || a.municipality_name.localeCompare(b.municipality_name, "es")
  );

  const gradeCount: Record<string, number> = {};
  for (const r of rows) {
    const g = r.ssl?.grade ?? "—";
    gradeCount[g] = (gradeCount[g] ?? 0) + 1;
  }
  const goodCount  = (gradeCount["A+"] ?? 0) + (gradeCount["A"] ?? 0);
  const warnCount  = (gradeCount["B"] ?? 0) + (gradeCount["C"] ?? 0);
  const badCount   = (gradeCount["D"] ?? 0) + (gradeCount["F"] ?? 0) + (gradeCount["T"] ?? 0) + (gradeCount["M"] ?? 0);

  const isEmpty = rows.length === 0;

  return (
    <div className="space-y-6">

      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{t("titulo")}</h1>
        <p className="text-slate-500 text-sm mt-1">{t("subtitulo")}</p>
      </div>

      {/* Summary cards */}
      {rows.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-white border border-slate-200 rounded-xl px-4 py-4 flex items-center gap-3 shadow-sm">
            <div className="bg-emerald-50 rounded-xl p-2.5 shrink-0"><CheckCircle2 className="w-5 h-5 text-emerald-600" /></div>
            <div>
              <p className="text-2xl font-black text-emerald-700 leading-none">{goodCount}</p>
              <p className="text-xs text-slate-500 mt-1">Grado A / A+</p>
            </div>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl px-4 py-4 flex items-center gap-3 shadow-sm">
            <div className="bg-orange-50 rounded-xl p-2.5 shrink-0"><AlertTriangle className="w-5 h-5 text-orange-500" /></div>
            <div>
              <p className="text-2xl font-black text-orange-600 leading-none">{warnCount}</p>
              <p className="text-xs text-slate-500 mt-1">Grado B / C</p>
            </div>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl px-4 py-4 flex items-center gap-3 shadow-sm">
            <div className="bg-red-50 rounded-xl p-2.5 shrink-0"><XCircle className="w-5 h-5 text-red-500" /></div>
            <div>
              <p className="text-2xl font-black text-red-600 leading-none">{badCount}</p>
              <p className="text-xs text-slate-500 mt-1">Grado D / F</p>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
        {isEmpty ? (
          <div className="text-center py-20 space-y-3">
            <Shield className="w-10 h-10 text-slate-200 mx-auto" />
            <p className="text-slate-400 text-sm font-medium">{t("sin_datos")}</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-slate-100 bg-slate-50/80">
              <tr>
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">{t("municipalidad")}</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide hidden md:table-cell">{t("provincia")}</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide hidden lg:table-cell">
                  <span className="flex items-center gap-1"><Globe className="w-3 h-3" /> {t("dominio")}</span>
                </th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">
                  <span className="flex items-center justify-center gap-1"><Shield className="w-3 h-3" /> SSL</span>
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide hidden sm:table-cell">{t("vence_cert")}</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide hidden sm:table-cell">{t("vence_dominio")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {rows.map((row) => (
                <tr key={row.municipality_id} className="hover:bg-slate-50/60 transition-colors">
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-800 text-sm">{row.municipality_name}</span>
                      {row.ssl?.has_warnings && (
                        <AlertTriangle className="w-3.5 h-3.5 text-orange-400 shrink-0" />
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3.5 text-xs text-slate-500 hidden md:table-cell">{row.province}</td>
                  <td className="px-4 py-3.5 hidden lg:table-cell">
                    <a href={`https://${row.domain}`} target="_blank" rel="noopener noreferrer"
                       className="text-xs text-slate-400 hover:text-blue-600 font-mono transition-colors">
                      {row.domain}
                    </a>
                  </td>
                  <td className="px-4 py-3.5 text-center">
                    <div className="flex justify-center">
                      <GradeCircle grade={row.ssl?.grade ?? null} />
                    </div>
                  </td>
                  <td className="px-4 py-3.5 hidden sm:table-cell">
                    <ExpiryBadge dateStr={row.ssl?.cert_expiry ?? null} />
                  </td>
                  <td className="px-4 py-3.5 hidden sm:table-cell">
                    <ExpiryBadge dateStr={row.domain_rec?.expiry_date ?? null} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
