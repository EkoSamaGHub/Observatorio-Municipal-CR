import Link from "next/link";
import { api } from "@/lib/api";
import CrawlProgress from "@/components/CrawlProgress";
import EffortCounter from "@/components/EffortCounter";

const PROVINCE_COLORS: Record<string, string> = {
  "San José":    "border-blue-500 bg-blue-50",
  "Alajuela":    "border-emerald-500 bg-emerald-50",
  "Cartago":     "border-purple-500 bg-purple-50",
  "Heredia":     "border-teal-500 bg-teal-50",
  "Guanacaste":  "border-orange-500 bg-orange-50",
  "Puntarenas":  "border-red-500 bg-red-50",
  "Limón":       "border-amber-500 bg-amber-50",
};

const PROVINCE_TEXT: Record<string, string> = {
  "San José":    "text-blue-700",
  "Alajuela":    "text-emerald-700",
  "Cartago":     "text-purple-700",
  "Heredia":     "text-teal-700",
  "Guanacaste":  "text-orange-700",
  "Puntarenas":  "text-red-700",
  "Limón":       "text-amber-700",
};

export default async function HomePage() {
  let municipalities: Awaited<ReturnType<typeof api.getMunicipalities>> = [];
  let runs: Awaited<ReturnType<typeof api.getRuns>> = [];
  let activeRun: Awaited<ReturnType<typeof api.getActiveRun>> = { active: false };

  try {
    [municipalities, runs, activeRun] = await Promise.all([
      api.getMunicipalities(),
      api.getRuns(),
      api.getActiveRun(),
    ]);
  } catch {
    // API offline — show empty state
  }

  const totalPages   = municipalities.reduce((s, m) => s + m.pages_crawled, 0);
  const totalDocs    = municipalities.reduce((s, m) => s + m.documents_found, 0);
  const totalChanges = municipalities.reduce((s, m) => s + m.changes_detected, 0);
  const lastRun      = runs[0] ?? null;

  const provinceMap: Record<string, number> = {};
  for (const m of municipalities) {
    provinceMap[m.province] = (provinceMap[m.province] ?? 0) + 1;
  }
  const provinces = Object.entries(provinceMap).sort(([a], [b]) => a.localeCompare(b));

  return (
    <>
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section className="bg-gradient-to-br from-blue-950 via-blue-900 to-blue-800 text-white">
        <div className="container mx-auto px-4 max-w-7xl py-16 text-center space-y-5">
          <div className="inline-flex items-center gap-2 bg-white/10 rounded-full px-4 py-1.5 text-sm font-medium text-blue-100 mb-2">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            Monitoreo activo · 84 municipalidades
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight">
            Observatorio Municipal<br />
            <span className="text-blue-300">de Costa Rica</span>
          </h1>
          <p className="text-lg text-blue-200 max-w-2xl mx-auto">
            Transparencia, documentos y seguimiento de cambios en los sitios web de las 84 municipalidades costarricenses.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <Link
              href="/municipalidades"
              className="bg-white text-blue-900 font-semibold px-6 py-3 rounded-lg hover:bg-blue-50 transition-colors shadow"
            >
              Ver municipalidades
            </Link>
            <Link
              href="/busqueda"
              className="border border-white/30 text-white font-medium px-6 py-3 rounded-lg hover:bg-white/10 transition-colors"
            >
              Buscar en todas →
            </Link>
          </div>
        </div>
      </section>

      {/* ── Stats bar ────────────────────────────────────────────────────── */}
      <section className="bg-white border-b border-slate-200 shadow-sm">
        <div className="container mx-auto px-4 max-w-7xl">
          <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-slate-100">
            <StatCard icon={<BuildingIcon />} value={municipalities.length || 84} label="Municipalidades" color="text-blue-700" />
            <StatCard icon={<PageIcon />}     value={totalPages}                  label="Páginas indexadas" color="text-slate-700" />
            <StatCard icon={<DocIcon />}      value={totalDocs}                   label="Documentos" color="text-emerald-700" />
            <StatCard icon={<BellIcon />}     value={totalChanges}                label="Cambios detectados" color="text-orange-600" />
          </div>
        </div>
      </section>

      <div className="container mx-auto px-4 max-w-7xl py-12 space-y-12">

        {/* ── Live widgets ──────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
          <CrawlProgress />
          <EffortCounter />
        </div>

        {/* ── Last run banner ───────────────────────────────────────────── */}
        {lastRun && (
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 bg-blue-50 border border-blue-200 rounded-xl px-5 py-4">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-blue-500 shrink-0" />
              <div className="text-sm text-blue-900">
                <span className="font-semibold">Última actualización: </span>
                {new Date(lastRun.finished_at ?? lastRun.started_at).toLocaleString("es-CR")}
              </div>
            </div>
            <div className="flex items-center gap-4 text-xs text-blue-700 font-medium pl-5 sm:pl-0">
              <span>{lastRun.pages_crawled.toLocaleString("es-CR")} páginas</span>
              <span className="text-blue-300">·</span>
              <span>{lastRun.pages_new} nuevas</span>
              <span className="text-blue-300">·</span>
              <span>{lastRun.pages_changed} cambios</span>
            </div>
          </div>
        )}

        {/* ── Province grid ─────────────────────────────────────────────── */}
        {provinces.length > 0 ? (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-bold text-slate-800">Provincias</h2>
              <Link href="/municipalidades" className="text-sm text-blue-600 hover:text-blue-800 font-medium">
                Ver todas las municipalidades →
              </Link>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {provinces.map(([province, count]) => (
                <Link
                  key={province}
                  href={`/municipalidades?provincia=${encodeURIComponent(province)}`}
                  className={`border-l-4 rounded-xl p-5 transition-all hover:shadow-md hover:-translate-y-0.5 ${PROVINCE_COLORS[province] ?? "border-slate-400 bg-slate-50"}`}
                >
                  <div className={`font-bold text-base ${PROVINCE_TEXT[province] ?? "text-slate-700"}`}>
                    {province}
                  </div>
                  <div className="text-2xl font-bold text-slate-800 mt-1">{count}</div>
                  <div className="text-xs text-slate-500 mt-0.5">municipalidades</div>
                </Link>
              ))}
            </div>
          </div>
        ) : (
          <div className="text-center py-20 space-y-3">
            <div className="text-4xl">🏛️</div>
            <p className="text-slate-500">Sin datos aún. Ejecute el pipeline para comenzar.</p>
            <code className="text-sm bg-slate-100 px-3 py-1 rounded text-slate-600">python pipeline.py --mode discover</code>
          </div>
        )}

        {/* ── Feature strip ─────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-4">
          <FeatureCard
            icon={<SearchIcon />}
            title="Búsqueda unificada"
            desc="Busca en el contenido de las 84 municipalidades desde un solo lugar."
            href="/busqueda"
          />
          <FeatureCard
            icon={<DocIcon />}
            title="Biblioteca de documentos"
            desc="PDFs, actas y licitaciones indexados y accesibles directamente."
            href="/documentos"
          />
          <FeatureCard
            icon={<BellIcon />}
            title="Detección de cambios"
            desc="Rastrea qué páginas municipales han cambiado y cuándo."
            href="/cambios"
          />
        </div>
      </div>
    </>
  );
}

/* ── Sub-components ────────────────────────────────────────────────────── */

function StatCard({ icon, value, label, color }: { icon: React.ReactNode; value: number; label: string; color: string }) {
  return (
    <div className="flex flex-col items-center gap-1.5 py-6 px-4 text-center">
      <div className={`${color} opacity-70`}>{icon}</div>
      <div className={`text-3xl font-bold ${color}`}>{value.toLocaleString("es-CR")}</div>
      <div className="text-xs text-slate-500 font-medium uppercase tracking-wide">{label}</div>
    </div>
  );
}

function FeatureCard({ icon, title, desc, href }: { icon: React.ReactNode; title: string; desc: string; href: string }) {
  return (
    <Link href={href} className="bg-white rounded-xl border border-slate-200 p-6 hover:border-blue-300 hover:shadow-md transition-all group">
      <div className="text-blue-600 mb-3 group-hover:text-blue-700">{icon}</div>
      <h3 className="font-semibold text-slate-800 mb-1">{title}</h3>
      <p className="text-sm text-slate-500">{desc}</p>
    </Link>
  );
}

/* ── Icons (inline SVG) ───────────────────────────────────────────────── */

function BuildingIcon() {
  return (
    <svg className="w-7 h-7" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 21v-8.25M15.75 21v-8.25M8.25 21v-8.25M3 9l9-6 9 6m-1.5 12V10.332A48.36 48.36 0 0 0 12 9.75c-2.551 0-5.056.2-7.5.582V21M3 21h18M12 6.75h.008v.008H12V6.75Z" />
    </svg>
  );
}

function PageIcon() {
  return (
    <svg className="w-7 h-7" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
    </svg>
  );
}

function DocIcon() {
  return (
    <svg className="w-7 h-7" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg className="w-7 h-7" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg className="w-7 h-7" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
    </svg>
  );
}
