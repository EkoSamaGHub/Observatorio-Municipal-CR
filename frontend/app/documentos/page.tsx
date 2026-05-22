import { getTranslations } from "next-intl/server";
import { api, Document } from "@/lib/api";
import { FileText, FileSpreadsheet, Archive, Map, FileCode, ExternalLink } from "lucide-react";

const FILE_ICONS: Record<string, React.ReactNode> = {
  pdf:  <FileText className="w-5 h-5 text-red-500" />,
  docx: <FileCode className="w-5 h-5 text-blue-500" />,
  xlsx: <FileSpreadsheet className="w-5 h-5 text-emerald-600" />,
  zip:  <Archive className="w-5 h-5 text-amber-500" />,
  gis:  <Map className="w-5 h-5 text-teal-500" />,
};

const FILE_BADGE: Record<string, string> = {
  pdf:  "bg-red-50 text-red-700 border-red-200",
  docx: "bg-blue-50 text-blue-700 border-blue-200",
  xlsx: "bg-emerald-50 text-emerald-700 border-emerald-200",
  zip:  "bg-amber-50 text-amber-700 border-amber-200",
  gis:  "bg-teal-50 text-teal-700 border-teal-200",
};

const FILE_TYPES = ["pdf", "docx", "xlsx", "zip", "gis"];

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

  return (
    <div className="space-y-6">

      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{t("titulo")}</h1>
        <p className="text-slate-500 text-sm mt-1">{t("subtitulo")}</p>
      </div>

      {/* Type filter */}
      <div className="flex flex-wrap gap-2">
        <a
          href="/documentos"
          className={`px-3.5 py-1.5 rounded-full text-xs font-semibold border transition-colors ${
            !tipo ? "bg-blue-600 text-white border-blue-600 shadow-sm" : "bg-white border-slate-200 text-slate-600 hover:border-blue-300"
          }`}
        >
          {t("todos_tipos")}
        </a>
        {FILE_TYPES.map((ft) => (
          <a
            key={ft}
            href={`/documentos?tipo=${ft}`}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold border uppercase tracking-wide transition-colors ${
              tipo === ft ? "bg-blue-600 text-white border-blue-600 shadow-sm" : "bg-white border-slate-200 text-slate-600 hover:border-blue-300"
            }`}
          >
            {ft}
          </a>
        ))}
      </div>

      {documents.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {documents.map((d) => {
            const ft = d.file_type ?? "pdf";
            const icon = FILE_ICONS[ft] ?? <FileText className="w-5 h-5 text-slate-400" />;
            const badge = FILE_BADGE[ft] ?? "bg-slate-50 text-slate-600 border-slate-200";
            const filename = (() => {
              try { return decodeURIComponent(d.url.split("/").pop()?.split("?")[0] ?? d.url); }
              catch { return d.url.split("/").pop() ?? d.url; }
            })();
            return (
              <a
                key={d.id}
                href={d.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group bg-white border border-slate-200 rounded-xl p-4 hover:border-blue-300 hover:shadow-md transition-all flex items-start gap-3"
              >
                <div className={`p-2 rounded-lg border ${badge} shrink-0`}>{icon}</div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-800 group-hover:text-blue-700 leading-snug line-clamp-2 transition-colors">
                    {filename}
                  </p>
                  <p className="text-xs text-slate-400 mt-1 font-mono">{d.municipality_id}</p>
                  <div className="flex items-center justify-between mt-2.5">
                    <span className={`text-xs font-bold px-1.5 py-0.5 rounded border uppercase ${badge}`}>{ft}</span>
                    <ExternalLink className="w-3.5 h-3.5 text-slate-300 group-hover:text-blue-400 transition-colors" />
                  </div>
                </div>
              </a>
            );
          })}
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-2xl text-center py-20 space-y-3">
          <FileText className="w-10 h-10 text-slate-200 mx-auto" />
          <p className="text-slate-400 text-sm font-medium">{t("sin_documentos")}</p>
        </div>
      )}
    </div>
  );
}
