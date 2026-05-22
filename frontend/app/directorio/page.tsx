import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { api, Municipality } from "@/lib/api";
import FaviconImage from "@/components/FaviconImage";
import { ExternalLink, ArrowRight } from "lucide-react";

const PROVINCES = ["San José","Alajuela","Cartago","Heredia","Guanacaste","Puntarenas","Limón"];

const PROVINCE_ISO: Record<string, string> = {
  "San José":   "CR-SJ",
  "Alajuela":   "CR-A",
  "Cartago":    "CR-C",
  "Heredia":    "CR-H",
  "Guanacaste": "CR-G",
  "Puntarenas": "CR-P",
  "Limón":      "CR-L",
};

const PROVINCE_GRADIENT: Record<string, string> = {
  "San José":   "from-blue-700 to-blue-900",
  "Alajuela":   "from-emerald-600 to-emerald-800",
  "Cartago":    "from-violet-600 to-violet-800",
  "Heredia":    "from-teal-600 to-teal-800",
  "Guanacaste": "from-orange-500 to-orange-700",
  "Puntarenas": "from-rose-600 to-rose-800",
  "Limón":      "from-amber-500 to-amber-700",
};

function faviconUrl(rootUrl: string): string {
  try {
    const { hostname } = new URL(rootUrl);
    return `https://www.google.com/s2/favicons?domain=${hostname}&sz=64`;
  } catch { return ""; }
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
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{t("titulo")}</h1>
        <p className="text-slate-500 text-sm mt-1">{t("subtitulo")}</p>
      </div>

      {PROVINCES.map((province) => {
        const munis = byProvince[province] ?? [];
        const iso = PROVINCE_ISO[province];
        const gradient = PROVINCE_GRADIENT[province] ?? "from-slate-600 to-slate-800";

        return (
          <section key={province}>
            {/* Province header */}
            <div className={`bg-gradient-to-r ${gradient} rounded-xl px-5 py-3 mb-4 flex items-center justify-between`}>
              <div className="flex items-center gap-3">
                <h2 className="text-base font-bold text-white">{province}</h2>
                <span className="text-xs font-mono font-semibold bg-white/20 text-white px-2 py-0.5 rounded-full border border-white/20">
                  {iso}
                </span>
              </div>
              <span className="text-xs text-white/70 font-medium">
                {munis.length} {t("municipalidades")}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
              {munis.map((m) => {
                const favicon = faviconUrl(m.root_url);
                const shortName = m.name.replace(/^Municipalidad\s+(de|del)\s+/i, "");
                return (
                  <div
                    key={m.id}
                    className="group bg-white border border-slate-200 rounded-xl p-4 flex flex-col items-center gap-3 hover:border-slate-300 hover:shadow-md transition-all"
                  >
                    <div className="w-12 h-12 rounded-xl overflow-hidden ring-2 ring-slate-100 group-hover:ring-blue-100 transition-all shrink-0">
                      <FaviconImage
                        src={favicon}
                        initial={shortName.charAt(0).toUpperCase()}
                        seed={m.id}
                      />
                    </div>
                    <div className="text-center">
                      <p className="text-xs font-bold text-slate-800 leading-snug line-clamp-2">{shortName}</p>
                      <p className="text-xs font-mono text-slate-400 mt-0.5">{m.id}</p>
                    </div>
                    <div className="flex flex-col gap-1.5 w-full mt-auto">
                      <a
                        href={m.root_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center justify-center gap-1 text-xs px-2 py-1.5 rounded-lg border border-slate-200 text-slate-500 hover:border-slate-300 hover:text-slate-700 transition-colors"
                      >
                        <ExternalLink className="w-3 h-3" /> {t("sitio_oficial")}
                      </a>
                      <Link
                        href={`/municipalidades/${m.id}`}
                        className="flex items-center justify-center gap-1 text-xs px-2 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors font-semibold"
                      >
                        {t("ver_perfil")} <ArrowRight className="w-3 h-3" />
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
        <div className="text-center py-16 text-slate-400 text-sm">Sin datos disponibles</div>
      )}
    </div>
  );
}
