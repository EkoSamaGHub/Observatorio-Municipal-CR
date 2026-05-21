import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { api } from "@/lib/api";

export default async function HomePage() {
  const t = await getTranslations("inicio");

  let municipalities: Awaited<ReturnType<typeof api.getMunicipalities>> = [];
  let runs: Awaited<ReturnType<typeof api.getRuns>> = [];

  try {
    [municipalities, runs] = await Promise.all([api.getMunicipalities(), api.getRuns()]);
  } catch {
    // API not reachable — show empty state
  }

  const totalDocs = municipalities.reduce((s, m) => s + m.documents_found, 0);
  const totalChanges = municipalities.reduce((s, m) => s + m.changes_detected, 0);
  const lastRun = runs[0] ?? null;
  const provinces = [...new Set(municipalities.map((m) => m.province))].sort();

  return (
    <div className="space-y-10">
      {/* Hero */}
      <div className="text-center space-y-3 py-8">
        <h1 className="text-4xl font-bold text-gray-900">{t("titulo")}</h1>
        <p className="text-xl text-gray-500 max-w-2xl mx-auto">{t("subtitulo")}</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <StatCard label={t("total_municipalidades")} value={municipalities.length || 84} color="blue" />
        <StatCard label={t("total_documentos")} value={totalDocs} color="green" />
        <StatCard label={t("total_cambios")} value={totalChanges} color="orange" />
      </div>

      {/* Last run */}
      {lastRun && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
          {t("ultima_actualizacion")}:{" "}
          <span className="font-medium">
            {new Date(lastRun.finished_at ?? lastRun.started_at).toLocaleString("es-CR")}
          </span>
          {" — "}
          {lastRun.pages_crawled} páginas · {lastRun.pages_new} nuevas · {lastRun.pages_changed} cambios
        </div>
      )}

      {/* Provinces */}
      {provinces.length > 0 ? (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold text-gray-800">
            {t("municipalidades_activas")} — {municipalities.length}
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {provinces.map((province) => {
              const count = municipalities.filter((m) => m.province === province).length;
              return (
                <Link
                  key={province}
                  href={`/municipalidades?provincia=${encodeURIComponent(province)}`}
                  className="bg-white border border-gray-200 rounded-lg p-4 hover:border-blue-400 hover:shadow-sm transition-all"
                >
                  <div className="font-semibold text-gray-800">{province}</div>
                  <div className="text-sm text-gray-500">{count} municipalidades</div>
                </Link>
              );
            })}
          </div>
          <div className="text-center pt-2">
            <Link
              href="/municipalidades"
              className="inline-block bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors font-medium"
            >
              {t("ver_todas")}
            </Link>
          </div>
        </div>
      ) : (
        <div className="text-center py-12 text-gray-400">{t("sin_datos")}</div>
      )}
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  const colors: Record<string, string> = {
    blue: "bg-blue-50 border-blue-200 text-blue-700",
    green: "bg-green-50 border-green-200 text-green-700",
    orange: "bg-orange-50 border-orange-200 text-orange-700",
  };
  return (
    <div className={`border rounded-lg p-6 text-center ${colors[color]}`}>
      <div className="text-4xl font-bold">{value.toLocaleString("es-CR")}</div>
      <div className="mt-1 text-sm font-medium opacity-80">{label}</div>
    </div>
  );
}
