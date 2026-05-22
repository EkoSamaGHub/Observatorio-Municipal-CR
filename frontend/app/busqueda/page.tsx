import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { api, SearchResult } from "@/lib/api";
import SearchForm from "@/components/SearchForm";
import { Search, FileText, Globe, Building2, ExternalLink } from "lucide-react";

export default async function BusquedaPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; tipo?: string }>;
}) {
  const t = await getTranslations("busqueda");
  const { q, tipo } = await searchParams;

  let results: { total: number; results: SearchResult[] } = { total: 0, results: [] };

  if (q && q.length >= 2) {
    try {
      results = await api.search(q, tipo);
    } catch {
      // API not reachable
    }
  }

  return (
    <div className="space-y-6">

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{t("titulo")}</h1>
        <p className="text-slate-500 text-sm mt-1">Busca en el contenido de las 84 municipalidades</p>
      </div>

      {/* Search form */}
      <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
        <SearchForm initialQ={q ?? ""} initialTipo={tipo ?? ""} />
      </div>

      {/* Results */}
      {q && (
        <div className="space-y-3">
          <p className="text-xs text-slate-500 font-medium">
            {results.total > 0 ? (
              <>
                <span className="font-bold text-slate-800">{results.total}</span> {t("resultados_para")}{" "}
                <span className="font-bold text-blue-700">&ldquo;{q}&rdquo;</span>
              </>
            ) : (
              <>{t("sin_resultados")} &ldquo;{q}&rdquo;</>
            )}
          </p>

          {results.results.length > 0 ? (
            <div className="space-y-2">
              {results.results.map((r, i) => (
                <ResultCard key={i} result={r} />
              ))}
            </div>
          ) : (
            <div className="bg-white border border-slate-200 rounded-2xl text-center py-16 space-y-3">
              <Search className="w-10 h-10 text-slate-200 mx-auto" />
              <p className="text-slate-400 text-sm font-medium">{t("sin_resultados")} &ldquo;{q}&rdquo;</p>
              <p className="text-xs text-slate-400">Intenta términos más generales o revisa la ortografía</p>
            </div>
          )}
        </div>
      )}

      {!q && (
        <div className="bg-white border border-slate-200 rounded-2xl text-center py-16 space-y-3">
          <Search className="w-10 h-10 text-slate-200 mx-auto" />
          <p className="text-slate-500 text-sm font-medium">Escribe algo para comenzar a buscar</p>
          <p className="text-xs text-slate-400">Busca por título de página, contenido o nombre de archivo</p>
        </div>
      )}
    </div>
  );
}

function ResultCard({ result: r }: { result: SearchResult }) {
  const isDoc = r.type === "document";
  const displayTitle = r.title || r.url.split("/").filter(Boolean).pop() || r.url;
  const date = r.last_crawled ?? r.last_seen;

  return (
    <div className="bg-white border border-slate-200 rounded-xl px-5 py-4 hover:border-blue-200 hover:shadow-sm transition-all group">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Meta row */}
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full border ${
              isDoc
                ? "bg-amber-50 text-amber-700 border-amber-200"
                : "bg-blue-50 text-blue-700 border-blue-200"
            }`}>
              {isDoc ? <FileText className="w-3 h-3" /> : <Globe className="w-3 h-3" />}
              {isDoc ? (r.file_type?.toUpperCase() ?? "DOC") : "Página"}
            </span>
            {r.municipality_name && (
              <Link
                href={`/municipalidades/${r.municipality_id}`}
                className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-blue-600 transition-colors"
              >
                <Building2 className="w-3 h-3" />
                {r.municipality_name}
              </Link>
            )}
            {date && (
              <span className="text-xs text-slate-400 ml-auto shrink-0">
                {new Date(date).toLocaleDateString("es-CR")}
              </span>
            )}
          </div>

          {/* Title */}
          <a
            href={r.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-bold text-slate-800 group-hover:text-blue-700 leading-snug block mb-1 transition-colors"
          >
            {displayTitle}
          </a>

          {/* URL */}
          <p className="text-xs text-slate-400 font-mono truncate mb-2">{r.url}</p>

          {/* Snippet */}
          {r.snippet && (
            <p className="text-xs text-slate-600 leading-relaxed line-clamp-2">{r.snippet}</p>
          )}
        </div>

        <a
          href={r.url}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 text-slate-300 hover:text-blue-500 transition-colors pt-0.5"
        >
          <ExternalLink className="w-4 h-4" />
        </a>
      </div>
    </div>
  );
}
