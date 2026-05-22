import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { api } from "@/lib/api";
import { notFound } from "next/navigation";

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
    { key: "paginas", label: t("tab_paginas"), count: muni.pages_crawled },
    { key: "documentos", label: t("tab_documentos"), count: muni.documents_found },
    { key: "cambios", label: t("tab_cambios"), count: muni.changes_detected },
  ];

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="text-sm text-gray-500">
        <Link href="/municipalidades" className="hover:text-blue-600">{t("../../municipalidades/titulo", { fallback: "Municipalidades" })}</Link>
        {" / "}
        <span className="text-gray-800">{muni.name}</span>
      </div>

      {/* Header */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{muni.name}</h1>
            <div className="text-gray-500 mt-1">
              {t("provincia")}: <span className="font-medium text-gray-700">{muni.province}</span>
            </div>
          </div>
          <a
            href={muni.root_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 text-sm font-medium"
          >
            {t("sitio_oficial")} ↗
          </a>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2">
          <MiniStat label={t("paginas")} value={muni.pages_crawled} />
          <MiniStat label={t("documentos")} value={muni.documents_found} />
          <MiniStat label={t("cambios_detectados")} value={muni.changes_detected} highlight={muni.changes_detected > 0} />
          <div className="text-center">
            <div className="text-xs text-gray-400 uppercase tracking-wide">{t("ultimo_rastreo")}</div>
            <div className="font-medium text-gray-700 text-sm mt-1">
              {muni.last_crawled
                ? new Date(muni.last_crawled).toLocaleDateString("es-CR")
                : t("sin_rastreo")}
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div>
        <div className="flex gap-1 border-b border-gray-200">
          {tabs.map(({ key, label, count }) => (
            <Link
              key={key}
              href={`/municipalidades/${id}?tab=${key}`}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                tab === key
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-800"
              }`}
            >
              {label}
              <span className="ml-1.5 text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded-full">
                {count}
              </span>
            </Link>
          ))}
        </div>

        <div className="mt-4">
          {tab === "paginas" && (
            <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
              {pages && pages.length > 0 ? (
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">URL</th>
                      <th className="text-center px-4 py-3 font-medium text-gray-600 hidden sm:table-cell">{t("profundidad")}</th>
                      <th className="text-center px-4 py-3 font-medium text-gray-600 hidden sm:table-cell">{t("estado")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {pages.map((p) => (
                      <tr key={p.id} className="hover:bg-gray-50">
                        <td className="px-4 py-2.5">
                          <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline truncate block max-w-md">
                            {p.url}
                          </a>
                        </td>
                        <td className="px-4 py-2.5 text-center text-gray-500 hidden sm:table-cell">{p.depth}</td>
                        <td className="px-4 py-2.5 text-center hidden sm:table-cell">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${p.status_code === 200 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                            {p.status_code}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="text-center py-10 text-gray-400">{t("sin_paginas")}</div>
              )}
            </div>
          )}

          {tab === "documentos" && (
            <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
              {documents && documents.length > 0 ? (
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">URL</th>
                      <th className="text-center px-4 py-3 font-medium text-gray-600 hidden sm:table-cell">{t("tipo")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {documents.map((d) => (
                      <tr key={d.id} className="hover:bg-gray-50">
                        <td className="px-4 py-2.5">
                          <a href={d.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline truncate block max-w-md">
                            {decodeURIComponent(d.url.split("/").pop() ?? d.url)}
                          </a>
                        </td>
                        <td className="px-4 py-2.5 text-center hidden sm:table-cell">
                          <span className="bg-red-50 text-red-700 text-xs font-medium px-2 py-0.5 rounded uppercase">
                            {d.file_type}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="text-center py-10 text-gray-400">{t("sin_documentos")}</div>
              )}
            </div>
          )}

          {tab === "cambios" && (
            <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
              {diffs && diffs.length > 0 ? (
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">URL</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 hidden sm:table-cell">{t("detectado")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {diffs.map((d) => (
                      <tr key={d.id} className="hover:bg-gray-50">
                        <td className="px-4 py-2.5">
                          <a href={d.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline truncate block max-w-md">
                            {d.url}
                          </a>
                        </td>
                        <td className="px-4 py-2.5 text-gray-500 text-xs hidden sm:table-cell">
                          {new Date(d.detected_at).toLocaleString("es-CR")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="text-center py-10 text-gray-400">{t("sin_cambios")}</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MiniStat({ label, value, highlight = false }: { label: string; value: number; highlight?: boolean }) {
  return (
    <div className="text-center">
      <div className="text-xs text-gray-400 uppercase tracking-wide">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${highlight ? "text-orange-600" : "text-gray-800"}`}>
        {value.toLocaleString("es-CR")}
      </div>
    </div>
  );
}
