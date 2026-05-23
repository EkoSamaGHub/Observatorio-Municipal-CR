import Link from "next/link";
import { Building2 } from "lucide-react";

const TECH_STACK = [
  // Frontend
  { label: "Next.js",      url: "https://nextjs.org",                           group: "Frontend" },
  { label: "React",        url: "https://react.dev",                            group: "Frontend" },
  { label: "Tailwind CSS", url: "https://tailwindcss.com",                      group: "Frontend" },
  { label: "TypeScript",   url: "https://www.typescriptlang.org",               group: "Frontend" },
  { label: "next-intl",    url: "https://next-intl.dev",                        group: "Frontend" },
  { label: "Lucide",       url: "https://lucide.dev",                           group: "Frontend" },
  { label: "Geist",        url: "https://vercel.com/font",                      group: "Frontend" },
  // Backend
  { label: "Python",       url: "https://www.python.org",                       group: "Backend" },
  { label: "FastAPI",      url: "https://fastapi.tiangolo.com",                 group: "Backend" },
  { label: "Pydantic",     url: "https://docs.pydantic.dev",                    group: "Backend" },
  { label: "Scrapling",    url: "https://github.com/D4Vinci/Scrapling",         group: "Backend" },
  { label: "Playwright",   url: "https://playwright.dev",                       group: "Backend" },
  { label: "pandas",       url: "https://pandas.pydata.org",                    group: "Backend" },
  { label: "pdfplumber",   url: "https://github.com/jsvine/pdfplumber",         group: "Backend" },
  { label: "PyMuPDF",      url: "https://pymupdf.readthedocs.io",               group: "Backend" },
  { label: "aiohttp",      url: "https://docs.aiohttp.org",                     group: "Backend" },
  // Data & Infra
  { label: "TimescaleDB",  url: "https://www.timescale.com",                    group: "Datos" },
  { label: "PostgreSQL",   url: "https://www.postgresql.org",                   group: "Datos" },
  { label: "Railway",      url: "https://railway.app",                          group: "Infra" },
  // AI
  { label: "Claude",       url: "https://claude.ai",                            group: "IA" },
] as const;

const GROUP_COLORS: Record<string, string> = {
  Frontend: "bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100",
  Backend:  "bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100",
  Datos:    "bg-violet-50 text-violet-700 border-violet-200 hover:bg-violet-100",
  Infra:    "bg-orange-50 text-orange-700 border-orange-200 hover:bg-orange-100",
  IA:       "bg-rose-50 text-rose-700 border-rose-200 hover:bg-rose-100",
};

const GROUPS = ["Frontend", "Backend", "Datos", "Infra", "IA"] as const;

export default function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white mt-16">
      {/* Identity row */}
      <div className="container mx-auto px-4 max-w-7xl pt-8 pb-4 flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-md bg-blue-900 flex items-center justify-center shrink-0">
            <Building2 className="w-4 h-4 text-white" strokeWidth={1.8} />
          </div>
          <span className="text-sm text-slate-600 font-medium">Observatorio Municipal de Costa Rica</span>
        </div>
        <div className="flex items-center gap-6 text-xs text-slate-400">
          <span>84 municipalidades</span>
          <span className="w-1 h-1 rounded-full bg-slate-300" />
          <span>Datos públicos</span>
          <span className="w-1 h-1 rounded-full bg-slate-300" />
          <span>© 2026</span>
        </div>
      </div>

      {/* Tech stack */}
      <div className="container mx-auto px-4 max-w-7xl pb-8">
        <div className="border-t border-slate-100 pt-5">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 mb-3">
            Construido con
          </p>
          <div className="flex flex-col gap-2.5">
            {GROUPS.map((group) => {
              const items = TECH_STACK.filter((t) => t.group === group);
              if (!items.length) return null;
              return (
                <div key={group} className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] font-semibold text-slate-400 w-14 shrink-0">{group}</span>
                  {items.map(({ label, url }) => (
                    <Link
                      key={label}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`
                        inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium
                        border transition-colors duration-150
                        ${GROUP_COLORS[group]}
                      `}
                    >
                      {label}
                    </Link>
                  ))}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </footer>
  );
}
