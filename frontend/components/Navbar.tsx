"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";

export default function Navbar() {
  const t = useTranslations("nav");
  const pathname = usePathname();

  const links = [
    { href: "/", label: t("inicio") },
    { href: "/municipalidades", label: t("municipalidades") },
    { href: "/documentos", label: t("documentos") },
    { href: "/cambios", label: t("cambios") },
    { href: "/busqueda", label: t("busqueda") },
  ];

  return (
    <nav className="bg-white border-b border-gray-200 shadow-sm">
      <div className="container mx-auto px-4 max-w-7xl flex items-center justify-between h-16">
        <Link href="/" className="flex items-center gap-2 font-bold text-blue-700 text-lg">
          <span className="text-2xl">🏛️</span>
          <span className="hidden sm:inline">Observatorio Municipal CR</span>
          <span className="sm:hidden">MUNI84CR</span>
        </Link>
        <div className="flex items-center gap-1">
          {links.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                pathname === href
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-600 hover:text-blue-700 hover:bg-gray-50"
              }`}
            >
              {label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}
