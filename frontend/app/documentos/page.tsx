import { getTranslations } from "next-intl/server";
import { api, Document } from "@/lib/api";

export default async function DocumentosPage({
  searchParams,
}: {
  searchParams: Promise<{ tipo?: string }>;
}) {
  const t = await getTranslations("documentos");
  const { tipo } = await searchParams;

  let documents: Document[] = [];
  try {
    documents = await api.getDocuments(tipo);
  } catch {
    // API not reachable
  }

  const fileTypes = ["pdf", "docx", "xlsx", "zip", "gis"];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">{t("titulo")}</h1>
        <p className="text-gray-500 mt-1">{t("subtitulo")}</p>
      </div>

      {/* Type filter */}
      <div className="flex flex-wrap gap-2">
        <a
          href="/documentos"
          className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${
            !tipo ? "bg-blue-600 text-white border-blue-600" : "border-gray-300 text-gray-600 hover:border-blue-400"
          }`}
        >
          {t("todos_tipos")}
        </a>
        {fileTypes.map((ft) => (
          <a
            key={ft}
            href={`/documentos?tipo=${ft}`}
            className={`px-3 py-1.5 rounded-full text-sm font-medium border uppercase transition-colors ${
              tipo === ft ? "bg-blue-600 text-white border-blue-600" : "border-gray-300 text-gray-600 hover:border-blue-400"
            }`}
          >
            {ft}
          </a>
        ))}
      </div>

      {/* Documents table */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        {documents.length > 0 ? (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Documento</th>
                <th className="text-center px-4 py-3 font-medium text-gray-600 hidden sm:table-cell">{t("tipo")}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600 hidden md:table-cell">{t("municipalidad")}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600 hidden lg:table-cell">{t("primera_vez")}</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {documents.map((d) => (
                <tr key={d.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2.5 max-w-xs">
                    <span className="truncate block text-gray-800">
                      {decodeURIComponent(d.url.split("/").pop() ?? d.url)}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-center hidden sm:table-cell">
                    <span className="bg-red-50 text-red-700 text-xs font-medium px-2 py-0.5 rounded uppercase">
                      {d.file_type}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-gray-500 hidden md:table-cell">{d.municipality_id}</td>
                  <td className="px-4 py-2.5 text-gray-400 text-xs hidden lg:table-cell">
                    {new Date(d.first_seen).toLocaleDateString("es-CR")}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <a
                      href={d.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:text-blue-800 font-medium"
                    >
                      {t("abrir")} ↗
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="text-center py-12 text-gray-400">No se encontraron documentos.</div>
        )}
      </div>
    </div>
  );
}
