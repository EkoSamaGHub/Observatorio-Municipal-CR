"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_LINKS = [
  { href: "/", label: "Inicio" },
  { href: "/municipalidades", label: "Municipalidades" },
  { href: "/documentos", label: "Documentos" },
  { href: "/cambios", label: "Cambios" },
  { href: "/busqueda", label: "Búsqueda" },
];

export default function Navbar() {
  const pathname = usePathname();

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
      {/* Top accent bar — CR colors */}
      <div className="h-1 bg-gradient-to-r from-blue-900 via-blue-600 to-red-600" />

      <div className="container mx-auto px-4 max-w-7xl flex items-center justify-between h-14">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 shrink-0">
          <div className="w-8 h-8 rounded bg-blue-900 flex items-center justify-center">
            <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5 text-white" stroke="currentColor" strokeWidth="1.8">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 21v-8.25M15.75 21v-8.25M8.25 21v-8.25M3 9l9-6 9 6m-1.5 12V10.332A48.36 48.36 0 0 0 12 9.75c-2.551 0-5.056.2-7.5.582V21M3 21h18M12 6.75h.008v.008H12V6.75Z" />
            </svg>
          </div>
          <div className="hidden sm:block">
            <span className="font-bold text-blue-900 text-sm leading-none">Observatorio Municipal</span>
            <span className="block text-xs text-slate-500 leading-none mt-0.5">Costa Rica · 84 municipalidades</span>
          </div>
          <span className="sm:hidden font-bold text-blue-900 text-sm">ObsMuni CR</span>
        </Link>

        {/* Nav links */}
        <nav className="flex items-center gap-0.5">
          {NAV_LINKS.map(({ href, label }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                  active
                    ? "bg-blue-50 text-blue-700"
                    : "text-slate-600 hover:text-blue-700 hover:bg-slate-50"
                }`}
              >
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
