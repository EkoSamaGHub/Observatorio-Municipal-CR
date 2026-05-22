import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { api, Municipality } from "@/lib/api";
import { Building2, ArrowRight, FileText, GitCompareArrows, BookOpen } from "lucide-react";

const PROVINCE_DOT: Record<string, string> = {
  "San José":   "bg-blue-500",
  "Alajuela":   "bg-emerald-500",
  "Cartago":    "bg-violet-500",
  "Heredia":    "bg-teal-500",
  "Guanacaste": "bg-orange-500",
  "Puntarenas": "bg-rose-500",
  "Limón":      "bg-amber-500",
};

const ALL_PROVINCES = ["San José","Alajuela","Cartago","Heredia","Guanacaste","Puntarenas","Limón"];

export default async function MunicipalidadesPage({
  searchParams,
}: {
  searchParams: Promise<{ provincia?: string }>;
}) {
  const t = await getTranslations("municipalidades");
  const { provincia } = await searchParams;

  let municipalities: Municipality[] = [];
  try {
    municipalities = await api.getMunicipalities(provincia);
  } catch {
    // API not reachable
  }

  const crawled = municipalities.filter((m) => m.pages_crawled > 0).length;

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end gap-4">
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{t("titulo")}</h1>
          <p className="text-slate-500 text-sm mt-1">{t("subtitulo")}</p>
        </div>
        {municipalities.length > 0 && (
          <div className="text-sm text-slate-500 shrink-0">
            <span className="font-bold text-slate-800">{crawled}</span> de {municipalities.length} rastreadas
          </div>
        )}
      </div>

      {/* Province filter */}
      <div className="flex flex-wrap gap-2">
        <Link
          href="/municipalidades"
          className={`px-3.5 py-1.5 rounded-full text-xs font-semibold border transition-colors ${
            !provincia
              ? "bg-blue-600 text-white border-blue-600 shadow-sm"
              : "border-slate-200 text-slate-600 hover:border-blue-300 hover:text-blue-700 bg-white"
          }`}
        >
          Todas las provincias
        </Link>
        {ALL_PROVINCES.map((p) => (
          <Link
            key={p}
            href={`/municipalidades?provincia=${encodeURIComponent(p)}`}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold border transition-colors ${
              provincia === p
                ? "bg-blue-600 text-white border-blue-600 shadow-sm"
                : "border-slate-200 text-slate-600 hover:border-blue-300 hover:text-blue-700 bg-white"
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${PROVINCE_DOT[p] ?? "bg-slate-400"}`} />
            {p}
          </Link>
        ))}
      </div>

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
        {municipalities.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/80">
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Municipalidad</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide hidden md:table-cell">Provincia</th>
                <th className="text-right px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide hidden sm:table-cell">
                  <span className="flex items-center justify-end gap-1"><BookOpen className="w-3 h-3" /> Páginas</span>
                </th>
                <th className="text-right px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide hidden sm:table-cell">
                  <span className="flex items-center justify-end gap-1"><FileText className="w-3 h-3" /> Docs</span>
                </th>
                <th className="text-right px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide hidden lg:table-cell">
                  <span className="flex items-center justify-end gap-1"><GitCompareArrows className="w-3 h-3" /> Cambios</span>
                </th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide hidden lg:table-cell">Rastreado</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {municipalities.map((m) => {
                const dot = PROVINCE_DOT[m.province] ?? "bg-slate-400";
                const hasCrawled = m.pages_crawled > 0;
                return (
                  <tr key={m.id} className="hover:bg-slate-50/70 transition-colors group">
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2.5">
                        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} />
                        <span className="font-semibold text-slate-800 text-sm">{m.name}</span>
                        {!hasCrawled && (
                          <span className="text-xs text-slate-400 border border-slate-200 rounded px-1.5 py-0.5 hidden sm:inline">sin datos</span>
                        )}
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-slate-500 text-xs hidden md:table-cell">{m.province}</td>
                    <td className="px-5 py-3.5 text-right hidden sm:table-cell">
                      <span className={`text-sm font-semibold ${hasCrawled ? "text-slate-800" : "text-slate-300"}`}>
                        {m.pages_crawled.toLocaleString("es-CR")}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right hidden sm:table-cell">
                      <span className={`text-sm font-semibold ${m.documents_found > 0 ? "text-emerald-700" : "text-slate-300"}`}>
                        {m.documents_found.toLocaleString("es-CR")}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right hidden lg:table-cell">
                      {m.changes_detected > 0 ? (
                        <span className="inline-flex items-center gap-1 text-xs font-semibold text-orange-600 bg-orange-50 border border-orange-200 rounded-full px-2 py-0.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                          {m.changes_detected}
                        </span>
                      ) : (
                        <span className="text-slate-300 text-sm">—</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-xs text-slate-400 hidden lg:table-cell">
                      {m.last_crawled
                        ? new Date(m.last_crawled).toLocaleDateString("es-CR")
                        : <span className="text-slate-300">—</span>}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <Link
                        href={`/municipalidades/${m.id}`}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800 opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        Perfil <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <div className="text-center py-16 space-y-3">
            <Building2 className="w-10 h-10 text-slate-300 mx-auto" />
            <p className="text-slate-400 text-sm">Sin datos disponibles</p>
          </div>
        )}
      </div>
    </div>
  );
}
