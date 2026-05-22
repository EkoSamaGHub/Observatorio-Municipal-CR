import Image from "next/image";
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { api, Municipality } from "@/lib/api";

const PROVINCES = [
  "San José",
  "Alajuela",
  "Cartago",
  "Heredia",
  "Guanacaste",
  "Puntarenas",
  "Limón",
];

const PROVINCE_ISO: Record<string, string> = {
  "San José":   "CR-SJ",
  "Alajuela":   "CR-A",
  "Cartago":    "CR-C",
  "Heredia":    "CR-H",
  "Guanacaste": "CR-G",
  "Puntarenas": "CR-P",
  "Limón":      "CR-L",
};

const PROVINCE_COLOR: Record<string, string> = {
  "San José":   "border-blue-700",
  "Alajuela":   "border-red-600",
  "Cartago":    "border-slate-600",
  "Heredia":    "border-green-700",
  "Guanacaste": "border-yellow-600",
  "Puntarenas": "border-teal-600",
  "Limón":      "border-orange-600",
};

function faviconUrl(rootUrl: string): string {
  try {
    const { hostname } = new URL(rootUrl);
    return `https://www.google.com/s2/favicons?domain=${hostname}&sz=64`;
  } catch {
    return "";
  }
}

export default async function DirectorioPage() {
  const t = await getTranslations("directorio");

  let municipalities: Municipality[] = [];
  try {
    municipalities = await api.getMunicipalities();
  } catch {
    // API not reachable
  }

  const byProvince = Object.fromEntries(
    PROVINCES.map((p) => [p, municipalities.filter((m) => m.province === p)])
  );

  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">{t("titulo")}</h1>
        <p className="text-gray-500 mt-1">{t("subtitulo")}</p>
      </div>

      {PROVINCES.map((province) => {
        const munis = byProvince[province] ?? [];
        const iso = PROVINCE_ISO[province];
        const borderColor = PROVINCE_COLOR[province] ?? "border-blue-700";

        return (
          <section key={province}>
            <div className={`flex items-center gap-3 border-b-2 ${borderColor} pb-2 mb-5`}>
              <h2 className="text-xl font-bold text-gray-900">{province}</h2>
              <span className="text-xs font-mono font-semibold bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded">
                {iso}
              </span>
              <span className="text-sm text-gray-400 ml-auto">
                {munis.length} {t("municipalidades")}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
              {munis.map((m) => {
                const favicon = faviconUrl(m.root_url);
                return (
                  <div
                    key={m.id}
                    className="bg-white border border-gray-200 rounded-lg p-4 flex flex-col items-center gap-3 hover:border-blue-300 hover:shadow-sm transition-all"
                  >
                    {/* Logo / favicon */}
                    <div className="w-12 h-12 rounded-lg bg-gray-50 border border-gray-100 flex items-center justify-center overflow-hidden shrink-0">
                      {favicon ? (
                        <Image
                          src={favicon}
                          alt=""
                          width={32}
                          height={32}
                          unoptimized
                          className="object-contain"
                        />
                      ) : (
                        <span className="text-lg font-bold text-blue-900">
                          {m.name.charAt(0)}
                        </span>
                      )}
                    </div>

                    {/* Name */}
                    <p className="text-center text-sm font-semibold text-gray-900 leading-tight line-clamp-2">
                      {m.name.replace(/^Municipalidad\s+(de|del)\s+/i, "")}
                    </p>

                    {/* ISO badge */}
                    <span className="text-xs font-mono bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded">
                      {m.id}
                    </span>

                    {/* Actions */}
                    <div className="flex flex-col gap-1.5 w-full mt-auto">
                      <a
                        href={m.root_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-center text-xs px-2 py-1.5 rounded border border-gray-200 text-gray-600 hover:border-blue-400 hover:text-blue-700 transition-colors"
                      >
                        {t("sitio_oficial")} ↗
                      </a>
                      <Link
                        href={`/municipalidades/${m.id}`}
                        className="text-center text-xs px-2 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                      >
                        {t("ver_perfil")}
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        );
      })}

      {municipalities.length === 0 && (
        <div className="text-center py-16 text-gray-400">Sin datos disponibles</div>
      )}
    </div>
  );
}
