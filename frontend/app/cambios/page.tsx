import { getTranslations } from "next-intl/server";
import { api } from "@/lib/api";

export default async function CambiosPage() {
  const t = await getTranslations("cambios");

  // Fetch diffs across all crawled municipalities by pulling the full list
  // then collecting diffs per municipality
  let allDiffs: Array<{
    id: number; municipality_id: string; url: string;
    old_hash: string | null; new_hash: string | null; detected_at: string;
  }> = [];

  try {
    const municipalities = await api.getMunicipalities();
    const crawled = municipalities.filter((m) => m.changes_detected > 0);
    const diffsPerMuni = await Promise.all(
      crawled.map((m) => api.getMunicipalityDiffs(m.id, 20))
    );
    allDiffs = diffsPerMuni
      .flat()
      .sort((a, b) => new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime());
  } catch {
    // API not reachable
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">{t("titulo")}</h1>
        <p className="text-gray-500 mt-1">{t("subtitulo")}</p>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        {allDiffs.length > 0 ? (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{t("municipalidad")}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{t("pagina")}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600 hidden sm:table-cell">{t("detectado")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {allDiffs.map((d) => (
                <tr key={d.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2.5 font-medium text-gray-700">{d.municipality_id}</td>
                  <td className="px-4 py-2.5">
                    <a href={d.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline truncate block max-w-sm">
                      {d.url}
                    </a>
                  </td>
                  <td className="px-4 py-2.5 text-gray-400 text-xs hidden sm:table-cell">
                    {new Date(d.detected_at).toLocaleString("es-CR")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="text-center py-12 text-gray-400">{t("sin_cambios")}</div>
        )}
      </div>
    </div>
  );
}
