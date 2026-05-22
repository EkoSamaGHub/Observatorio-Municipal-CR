import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { api } from "@/lib/api";
import { notFound } from "next/navigation";
import {
  BookOpen,
  FileText,
  GitCompareArrows,
  Globe,
  ArrowLeft,
  CalendarDays,
  ExternalLink,
} from "lucide-react";

export default async function MunicipalidadPerfilPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string }>;
}) {
  const t = await getTranslations("perfil");
  const { id } = await params;
  const { tab = "paginas" } = await searchParams;

  let muni, pages, documents, diffs;
  try {
    [muni, pages, documents, diffs] = await Promise.all([
      api.getMunicipality(id),
      api.getMunicipalityPages(id),
      api.getMunicipalityDocuments(id),
      api.getMunicipalityDiffs(id),
    ]);
  } catch {
    notFound();
  }

  const tabs = [
    { key: "paginas",    label: t("tab_paginas"),    icon: BookOpen,          count: muni.pages_crawled },
    { key: "documentos", label: t("tab_documentos"), icon: FileText,          count: muni.documents_found },
    { key: "cambios",    label: t("tab_cambios"),    icon: GitCompareArrows,  count: muni.changes_detected },
  ];

  const shortName = muni.name.replace(/^Municipalidad\s+(de|del)\s+/i, "");

  return (
    <div className="space-y-5">

      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm">
        <Link href="/municipalidades" className="flex items-center gap-1 text-slate-400 hover:text-blue-600 font-medium transition-colors">
          <ArrowLeft className="w-3.5 h-3.5" />
          Municipalidades
        </Link>
        <span className="text-slate-300">/</span>
        <span className="text-slate-600 font-medium">{shortName}</span>
      </div>

      {/* Profile header */}
      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
        <div className="bg-gradient-to-r from-blue-900 to-blue-800 px-6 py-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-blue-300 text-xs font-semibold uppercase tracking-widest mb-1">{muni.province}</p>
              <h1 className="text-2xl font-bold text-white tracking-tight">{muni.name}</h1>
              <p className="text-blue-300 text-xs font-mono mt-1">{muni.id}</p>
            </div>
            <a
              href={muni.root_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-xs font-semibold bg-white/15 hover:bg-white/25 text-white border border-white/20 rounded-lg px-3 py-2 transition-colors shrink-0"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              {t("sitio_oficial")}
            </a>
          </div>
        </div>

        {/* Stats strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-slate-100">
          <ProfileStat label={t("paginas")}            value={muni.pages_crawled}    color="text-blue-700" />
          <ProfileStat label={t("documentos")}         value={muni.documents_found}  color="text-emerald-700" />
          <ProfileStat label={t("cambios_detectados")} value={muni.changes_detected} color={muni.changes_detected > 0 ? "text-orange-600" : "text-slate-400"} />
          <div className="px-5 py-4 text-center">
            <p className="text-xs text-slate-400 uppercase tracking-wide font-semibold mb-1 flex items-center justify-center gap-1">
              <CalendarDays className="w-3 h-3" /> {t("ultimo_rastreo")}
            </p>
            <p className="text-sm font-semibold text-slate-700">
              {muni.last_crawled
                ? new Date(muni.last_crawled).toLocaleDateString("es-CR")
                : <span className="text-slate-300 font-normal">{t("sin_rastreo")}</span>}
            </p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
        <div className="flex border-b border-slate-100 bg-slate-50/60 px-1 pt-1">
          {tabs.map(({ key, label, icon: Icon, count }) => {
            const active = tab === key;
            return (
              <Link
                key={key}
                href={`/municipalidades/${id}?tab=${key}`}
                className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold rounded-t-lg transition-all mr-0.5 ${
                  active
                    ? "bg-white text-blue-700 border border-b-0 border-slate-200 shadow-sm"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                <Icon className="w-3.5 h-3.5" strokeWidth={active ? 2.2 : 1.8} />
                {label}
                <span className={`text-xs px-1.5 py-0.5 rounded-full font-bold ${active ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-500"}`}>
                  {count}
                </span>
              </Link>
            );
          })}
        </div>

        <div className="p-0">
          {tab === "paginas" && (
            pages && pages.length > 0 ? (
              <table className="w-full text-sm">
                <thead className="border-b border-slate-100 bg-slate-50/40">
                  <tr>
                    <th className="text-left px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">{t("pagina")}</th>
                    <th className="text-center px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide hidden sm:table-cell">{t("profundidad")}</th>
                    <th className="text-center px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide hidden sm:table-cell">{t("estado")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {pages.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-5 py-3.5">
                        <a href={p.url} target="_blank" rel="noopener noreferrer" className="group flex items-start gap-2">
                          <Globe className="w-3.5 h-3.5 text-slate-300 group-hover:text-blue-500 transition-colors mt-0.5 shrink-0" />
                          <div>
                            <p className="text-sm font-semibold text-blue-700 group-hover:underline leading-snug">
                              {p.title || p.url.split("/").filter(Boolean).pop() || p.url}
                            </p>
                            <p className="text-xs text-slate-400 truncate max-w-sm mt-0.5">{p.url}</p>
                            {p.snippet && (
                              <p className="text-xs text-slate-500 mt-1 line-clamp-1">{p.snippet}</p>
                            )}
                          </div>
                        </a>
                      </td>
                      <td className="px-4 py-3.5 text-center hidden sm:table-cell">
                        <span className="text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">{p.depth}</span>
                      </td>
                      <td className="px-4 py-3.5 text-center hidden sm:table-cell">
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                          p.status_code === 200
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-red-50 text-red-700 border border-red-200"
                        }`}>
                          {p.status_code ?? "—"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <EmptyState icon={<BookOpen className="w-8 h-8 text-slate-300" />} message={t("sin_paginas")} />
            )
          )}

          {tab === "documentos" && (
            documents && documents.length > 0 ? (
              <table className="w-full text-sm">
                <thead className="border-b border-slate-100 bg-slate-50/40">
                  <tr>
                    <th className="text-left px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">Archivo</th>
                    <th className="text-center px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide hidden sm:table-cell">{t("tipo")}</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide hidden md:table-cell">Visto</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {documents.map((d) => (
                    <tr key={d.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-5 py-3.5">
                        <a href={d.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 group">
                          <FileText className="w-4 h-4 text-slate-300 group-hover:text-blue-500 transition-colors shrink-0" />
                          <span className="text-sm font-medium text-blue-700 group-hover:underline truncate max-w-xs">
                            {decodeURIComponent(d.url.split("/").pop() ?? d.url)}
                          </span>
                        </a>
                      </td>
                      <td className="px-4 py-3.5 text-center hidden sm:table-cell">
                        <span className="text-xs font-bold px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 uppercase">
                          {d.file_type ?? "?"}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-xs text-slate-400 hidden md:table-cell">
                        {new Date(d.last_seen).toLocaleDateString("es-CR")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <EmptyState icon={<FileText className="w-8 h-8 text-slate-300" />} message={t("sin_documentos")} />
            )
          )}

          {tab === "cambios" && (
            diffs && diffs.length > 0 ? (
              <div className="divide-y divide-slate-50">
                {diffs.map((d) => (
                  <div key={d.id} className="px-5 py-4 hover:bg-slate-50/60 transition-colors flex items-start gap-4">
                    <div className="w-1.5 h-1.5 rounded-full bg-orange-400 mt-2 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <a href={d.url} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-700 hover:underline font-medium truncate block">
                        {d.url}
                      </a>
                      <div className="flex items-center gap-3 mt-1">
                        <span className="text-xs text-slate-400">
                          {new Date(d.detected_at).toLocaleString("es-CR")}
                        </span>
                        {d.old_hash && (
                          <span className="text-xs font-mono text-slate-300">
                            {d.old_hash.slice(0, 7)} → {(d.new_hash ?? "").slice(0, 7)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState icon={<GitCompareArrows className="w-8 h-8 text-slate-300" />} message={t("sin_cambios")} />
            )
          )}
        </div>
      </div>
    </div>
  );
}

function ProfileStat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="px-5 py-4 text-center">
      <p className="text-xs text-slate-400 uppercase tracking-wide font-semibold mb-1">{label}</p>
      <p className={`text-2xl font-black ${color}`}>{value.toLocaleString("es-CR")}</p>
    </div>
  );
}

function EmptyState({ icon, message }: { icon: React.ReactNode; message: string }) {
  return (
    <div className="text-center py-14 space-y-2">
      <div className="flex justify-center">{icon}</div>
      <p className="text-sm text-slate-400">{message}</p>
    </div>
  );
}
