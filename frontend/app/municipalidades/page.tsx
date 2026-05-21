import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { api, Municipality } from "@/lib/api";

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

  const allProvinces = [
    "San José", "Alajuela", "Cartago", "Heredia", "Guanacaste", "Puntarenas", "Limón",
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">{t("titulo")}</h1>
        <p className="text-gray-500 mt-1">{t("subtitulo")}</p>
      </div>

      {/* Province filter */}
      <div className="flex flex-wrap gap-2">
        <Link
          href="/municipalidades"
          className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${
            !provincia
              ? "bg-blue-600 text-white border-blue-600"
              : "border-gray-300 text-gray-600 hover:border-blue-400"
          }`}
        >
          {t("todas_provincias")}
        </Link>
        {allProvinces.map((p) => (
          <Link
            key={p}
            href={`/municipalidades?provincia=${encodeURIComponent(p)}`}
            className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${
              provincia === p
                ? "bg-blue-600 text-white border-blue-600"
                : "border-gray-300 text-gray-600 hover:border-blue-400"
            }`}
          >
            {p}
          </Link>
        ))}
      </div>

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Municipalidad</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600 hidden md:table-cell">Provincia</th>
              <th className="text-right px-4 py-3 font-medium text-gray-600 hidden sm:table-cell">{t("paginas_crawleadas")}</th>
              <th className="text-right px-4 py-3 font-medium text-gray-600 hidden sm:table-cell">{t("documentos")}</th>
              <th className="text-right px-4 py-3 font-medium text-gray-600 hidden lg:table-cell">{t("cambios")}</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600 hidden lg:table-cell">{t("ultimo_rastreo")}</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {municipalities.map((m) => (
              <tr key={m.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 font-medium text-gray-900">{m.name}</td>
                <td className="px-4 py-3 text-gray-500 hidden md:table-cell">{m.province}</td>
                <td className="px-4 py-3 text-right text-gray-700 hidden sm:table-cell">
                  {m.pages_crawled.toLocaleString("es-CR")}
                </td>
                <td className="px-4 py-3 text-right text-gray-700 hidden sm:table-cell">
                  {m.documents_found.toLocaleString("es-CR")}
                </td>
                <td className="px-4 py-3 text-right hidden lg:table-cell">
                  {m.changes_detected > 0 ? (
                    <span className="text-orange-600 font-medium">{m.changes_detected}</span>
                  ) : (
                    <span className="text-gray-400">0</span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-400 text-xs hidden lg:table-cell">
                  {m.last_crawled
                    ? new Date(m.last_crawled).toLocaleDateString("es-CR")
                    : t("sin_rastreo")}
                </td>
                <td className="px-4 py-3 text-right">
                  <Link
                    href={`/municipalidades/${m.id}`}
                    className="text-blue-600 hover:text-blue-800 font-medium"
                  >
                    {t("ver_perfil")} →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {municipalities.length === 0 && (
          <div className="text-center py-12 text-gray-400">Sin datos disponibles</div>
        )}
      </div>
    </div>
  );
}
