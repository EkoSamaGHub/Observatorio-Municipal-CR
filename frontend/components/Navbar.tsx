"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Building2,
  LayoutGrid,
  Shield,
  FileText,
  GitCompareArrows,
  Search,
  Map,
} from "lucide-react";

const NAV_LINKS = [
  { href: "/",                   label: "Inicio",          icon: Building2 },
  { href: "/municipalidades",    label: "Municipalidades", icon: LayoutGrid },
  { href: "/directorio",         label: "Directorio",      icon: Map },
  { href: "/documentos",         label: "Documentos",      icon: FileText },
  { href: "/cambios",            label: "Cambios",         icon: GitCompareArrows },
  { href: "/reportes/seguridad", label: "Seguridad",       icon: Shield },
  { href: "/busqueda",           label: "Búsqueda",        icon: Search },
];

export default function Navbar() {
  const pathname = usePathname();

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
      {/* CR accent bar */}
      <div className="h-0.5 bg-gradient-to-r from-blue-800 via-blue-500 to-red-600" />

      <div className="container mx-auto px-4 max-w-7xl flex items-center h-14 gap-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 shrink-0 group">
          <div className="w-8 h-8 rounded-lg bg-blue-900 flex items-center justify-center shadow-sm group-hover:bg-blue-800 transition-colors">
            <Building2 className="w-4.5 h-4.5 text-white" strokeWidth={1.8} />
          </div>
          <div className="hidden md:block leading-tight">
            <p className="text-sm font-bold text-blue-950 tracking-tight">Observatorio Municipal</p>
            <p className="text-[10px] text-slate-400 font-medium tracking-wide uppercase">Costa Rica · 84 municipalidades</p>
          </div>
          <span className="md:hidden text-sm font-bold text-blue-950">ObsMuni CR</span>
        </Link>

        {/* Divider */}
        <div className="hidden md:block h-5 w-px bg-slate-200" />

        {/* Nav */}
        <nav className="flex items-center gap-0.5 overflow-x-auto flex-1 no-scrollbar">
          {NAV_LINKS.map(({ href, label, icon: Icon }) => {
            const active = isActive(href);
            return (
              <Link
                key={href}
                href={href}
                className={`
                  flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all
                  ${active
                    ? "bg-blue-50 text-blue-700 shadow-sm"
                    : "text-slate-500 hover:text-slate-800 hover:bg-slate-50"
                  }
                `}
              >
                <Icon
                  className={`w-3.5 h-3.5 shrink-0 ${active ? "text-blue-600" : "text-slate-400"}`}
                  strokeWidth={active ? 2.2 : 1.8}
                />
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
