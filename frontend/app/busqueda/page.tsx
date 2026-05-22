import { getTranslations } from "next-intl/server";
import { api } from "@/lib/api";
import SearchForm from "@/components/SearchForm";

export default async function BusquedaPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; tipo?: string }>;
}) {
  const t = await getTranslations("busqueda");
  const { q, tipo } = await searchParams;

  let results: { total: number; results: Awaited<ReturnType<typeof api.search>>["results"] } = {
    total: 0,
    results: [],
  };

  if (q && q.length >= 2) {
    try {
      results = await api.search(q, tipo);
    } catch {
      // API not reachable
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">{t("titulo")}</h1>
      </div>

      <SearchForm initialQ={q ?? ""} initialTipo={tipo ?? ""} />

      {q && (
        <div>
          <p className="text-sm text-gray-500 mb-4">
            <span className="font-medium">{results.total}</span> {t("resultados")} &ldquo;{q}&rdquo;
          </p>

          {results.results.length > 0 ? (
            <div className="space-y-2">
              {results.results.map((r, i) => (
                <div key={i} className="bg-white border border-gray-200 rounded-lg px-4 py-3 hover:border-blue-300 transition-colors">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded uppercase ${
                      r.type === "document"
                        ? "bg-red-50 text-red-700"
                        : "bg-blue-50 text-blue-700"
                    }`}>
                      {r.type === "document" ? t("tipo_documento") : t("tipo_pagina")}
                    </span>
                    <span className="text-xs text-gray-400">{r.municipality_id}</span>
                  </div>
                  <a
                    href={r.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline text-sm truncate block"
                  >
                    {r.url}
                  </a>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-400">
              {t("sin_resultados")} &ldquo;{q}&rdquo;
            </div>
          )}
        </div>
      )}
    </div>
  );
}
