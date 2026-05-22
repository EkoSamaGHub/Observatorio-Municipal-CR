import Link from "next/link";
import { api } from "@/lib/api";
import CrawlProgress from "@/components/CrawlProgress";
import EffortCounter from "@/components/EffortCounter";
import {
  Building2,
  FileText,
  Bell,
  Search,
  Shield,
  GitCompareArrows,
  ArrowRight,
  Globe,
  BookOpen,
  LayoutGrid,
} from "lucide-react";

const PROVINCE_ACCENT: Record<string, string> = {
  "San José":   "from-blue-600 to-blue-800",
  "Alajuela":   "from-emerald-500 to-emerald-700",
  "Cartago":    "from-violet-500 to-violet-700",
  "Heredia":    "from-teal-500 to-teal-700",
  "Guanacaste": "from-orange-500 to-orange-700",
  "Puntarenas": "from-rose-500 to-rose-700",
  "Limón":      "from-amber-500 to-amber-700",
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
    // API offline
  }

  const totalPages   = municipalities.reduce((s, m) => s + m.pages_crawled, 0);
  const totalDocs    = municipalities.reduce((s, m) => s + m.documents_found, 0);
  const totalChanges = municipalities.reduce((s, m) => s + m.changes_detected, 0);
  const lastRun      = runs[0] ?? null;

  const provinceMap: Record<string, { count: number; pages: number; docs: number }> = {};
  for (const m of municipalities) {
    if (!provinceMap[m.province]) provinceMap[m.province] = { count: 0, pages: 0, docs: 0 };
    provinceMap[m.province].count++;
    provinceMap[m.province].pages += m.pages_crawled;
    provinceMap[m.province].docs  += m.documents_found;
  }
  const provinces = Object.entries(provinceMap).sort(([a], [b]) => a.localeCompare(b, "es"));

  return (
    <div className="space-y-6">

      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section className="relative bg-gradient-to-br from-blue-950 via-blue-900 to-blue-800 rounded-2xl overflow-hidden text-white shadow-xl">
        <div className="absolute -top-24 -right-24 w-96 h-96 rounded-full border border-white/5 pointer-events-none" />
        <div className="absolute -top-12 -right-12 w-64 h-64 rounded-full border border-white/5 pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />

        <div className="relative px-8 py-12 md:py-16 text-center space-y-5">
          <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur-sm rounded-full px-4 py-1.5 text-xs font-semibold text-blue-100 border border-white/10">
            {activeRun.active ? (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                Rastreo activo · {activeRun.municipalities_done ?? 0}/{activeRun.municipalities_total ?? 84} municipalidades
              </>
            ) : (
              <>
                <Globe className="w-3.5 h-3.5" />
                Monitoreo continuo · 84 municipalidades · Costa Rica
              </>
            )}
          </div>

          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight leading-tight">
            Observatorio Municipal
            <span className="block text-blue-300 mt-1">de Costa Rica</span>
          </h1>
          <p className="text-blue-200 max-w-xl mx-auto text-base leading-relaxed">
            Transparencia, documentos y seguimiento de cambios en los sitios web
            de las 84 municipalidades costarricenses.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <Link
              href="/municipalidades"
              className="flex items-center gap-2 bg-white text-blue-900 font-semibold px-6 py-2.5 rounded-xl hover:bg-blue-50 transition-colors shadow-lg text-sm"
            >
              <LayoutGrid className="w-4 h-4" />
              Ver municipalidades
            </Link>
            <Link
              href="/busqueda"
              className="flex items-center gap-2 border border-white/30 text-white font-medium px-6 py-2.5 rounded-xl hover:bg-white/10 transition-colors text-sm"
            >
              <Search className="w-4 h-4" />
              Búsqueda unificada
            </Link>
          </div>
        </div>
      </section>

      {/* ── Stats ──────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard icon={<Building2 className="w-5 h-5" />}  value={(municipalities.length || 84).toLocaleString("es-CR")} label="Municipalidades"   color="text-blue-700"    bg="bg-blue-50" />
        <StatCard icon={<BookOpen className="w-5 h-5" />}   value={totalPages.toLocaleString("es-CR")}                    label="Páginas indexadas" color="text-slate-700"   bg="bg-slate-100" />
        <StatCard icon={<FileText className="w-5 h-5" />}   value={totalDocs.toLocaleString("es-CR")}                     label="Documentos"        color="text-emerald-700" bg="bg-emerald-50" />
        <StatCard icon={<Bell className="w-5 h-5" />}       value={totalChanges.toLocaleString("es-CR")}                  label="Cambios"           color="text-orange-600"  bg="bg-orange-50" />
      </div>

      {/* ── Live widgets ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <CrawlProgress />
        <EffortCounter />
      </div>

      {/* ── Last run ─────────────────────────────────────────────────────── */}
      {lastRun && (
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 bg-white border border-slate-200 rounded-xl px-5 py-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-blue-500 shrink-0" />
            <p className="text-sm text-slate-700">
              <span className="font-semibold">Última actualización:</span>{" "}
              {new Date(lastRun.finished_at ?? lastRun.started_at).toLocaleString("es-CR")}
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-500 pl-5 sm:pl-0 flex-wrap">
            <span><span className="font-bold text-slate-800">{lastRun.pages_crawled.toLocaleString("es-CR")}</span> páginas</span>
            <span className="w-1 h-1 rounded-full bg-slate-300" />
            <span><span className="font-bold text-emerald-700">{lastRun.pages_new}</span> nuevas</span>
            <span className="w-1 h-1 rounded-full bg-slate-300" />
            <span><span className="font-bold text-orange-600">{lastRun.pages_changed}</span> cambios</span>
          </div>
        </div>
      )}

      {/* ── Province grid ────────────────────────────────────────────────── */}
      {provinces.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-800 tracking-tight">Por provincia</h2>
            <Link href="/municipalidades" className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800 font-semibold transition-colors">
              Ver todas <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {provinces.map(([province, data]) => {
              const gradient = PROVINCE_ACCENT[province] ?? "from-slate-500 to-slate-700";
              return (
                <Link
                  key={province}
                  href={`/municipalidades?provincia=${encodeURIComponent(province)}`}
                  className="group bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md hover:-translate-y-0.5 transition-all hover:border-slate-300"
                >
                  <div className={`w-9 h-9 rounded-xl bg-gradient-to-br ${gradient} flex items-center justify-center mb-3 shadow-sm group-hover:scale-105 transition-transform`}>
                    <Building2 className="w-4.5 h-4.5 text-white" strokeWidth={1.8} />
                  </div>
                  <p className="font-bold text-slate-800 text-sm leading-tight">{province}</p>
                  <p className="text-3xl font-black text-slate-900 mt-1 leading-none">{data.count}</p>
                  <p className="text-xs text-slate-400 mt-0.5">municipalidades</p>
                  {(data.pages > 0 || data.docs > 0) && (
                    <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-100 text-xs text-slate-500">
                      <span>{data.pages.toLocaleString("es-CR")} pág.</span>
                      {data.docs > 0 && (
                        <>
                          <span className="w-1 h-1 rounded-full bg-slate-300" />
                          <span>{data.docs.toLocaleString("es-CR")} docs</span>
                        </>
                      )}
                    </div>
                  )}
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Feature strip ────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <FeatureCard icon={<Search className="w-5 h-5" />}          title="Búsqueda unificada"   desc="Busca títulos y contenido en las 84 municipalidades."                 href="/busqueda"           accent="text-blue-600"    bg="bg-blue-50" />
        <FeatureCard icon={<Shield className="w-5 h-5" />}          title="Seguridad y dominios" desc="Grados SSL, certificados y fechas de vencimiento de dominio."         href="/reportes/seguridad" accent="text-emerald-700"  bg="bg-emerald-50" />
        <FeatureCard icon={<GitCompareArrows className="w-5 h-5" />} title="Cambios detectados"   desc="Rastrea qué páginas municipales han cambiado y cuándo."               href="/cambios"            accent="text-orange-600"  bg="bg-orange-50" />
      </div>

      {/* ── Empty state ──────────────────────────────────────────────────── */}
      {municipalities.length === 0 && (
        <div className="text-center py-20 space-y-4 bg-white rounded-2xl border border-slate-200">
          <Building2 className="w-12 h-12 text-slate-300 mx-auto" />
          <p className="text-slate-500 font-semibold">Sin datos aún</p>
          <code className="text-xs bg-slate-100 px-3 py-1.5 rounded-lg text-slate-600 inline-block">
            python pipeline.py --mode discover
          </code>
        </div>
      )}
    </div>
  );
}

function StatCard({ icon, value, label, color, bg }: {
  icon: React.ReactNode; value: string; label: string; color: string; bg: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 px-4 py-4 flex items-center gap-3 shadow-sm">
      <div className={`${bg} ${color} rounded-xl p-2.5 shrink-0`}>{icon}</div>
      <div className="min-w-0">
        <p className={`text-2xl font-black ${color} leading-none`}>{value}</p>
        <p className="text-xs text-slate-500 font-medium mt-1 leading-tight">{label}</p>
      </div>
    </div>
  );
}

function FeatureCard({ icon, title, desc, href, accent, bg }: {
  icon: React.ReactNode; title: string; desc: string; href: string; accent: string; bg: string;
}) {
  return (
    <Link href={href} className="group bg-white rounded-xl border border-slate-200 p-6 hover:border-slate-300 hover:shadow-md transition-all">
      <div className={`${bg} ${accent} rounded-xl p-2.5 w-fit mb-4 group-hover:scale-105 transition-transform`}>
        {icon}
      </div>
      <h3 className="font-bold text-slate-800 text-sm mb-1">{title}</h3>
      <p className="text-xs text-slate-500 leading-relaxed">{desc}</p>
      <div className={`flex items-center gap-1 mt-4 text-xs font-bold ${accent}`}>
        Explorar <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
      </div>
    </Link>
  );
}
