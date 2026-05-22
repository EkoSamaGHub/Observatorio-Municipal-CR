"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Search } from "lucide-react";

export default function SearchForm({
  initialQ,
  initialTipo,
}: {
  initialQ: string;
  initialTipo: string;
}) {
  const t = useTranslations("busqueda");
  const router = useRouter();
  const [q, setQ] = useState(initialQ);
  const [tipo, setTipo] = useState(initialTipo);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const params = new URLSearchParams();
    if (q.trim()) params.set("q", q.trim());
    if (tipo) params.set("tipo", tipo);
    router.push(`/busqueda?${params.toString()}`);
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 flex-wrap">
      <div className="flex-1 min-w-48 relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t("placeholder")}
          className="w-full pl-9 pr-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-slate-50 placeholder:text-slate-400"
        />
      </div>
      <select
        value={tipo}
        onChange={(e) => setTipo(e.target.value)}
        className="border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-slate-50 text-slate-600 font-medium"
      >
        <option value="">{t("todos")}</option>
        <option value="page">{t("tipo_pagina")}</option>
        <option value="document">{t("tipo_documento")}</option>
      </select>
      <button
        type="submit"
        className="flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-blue-700 transition-colors shadow-sm"
      >
        <Search className="w-4 h-4" />
        Buscar
      </button>
    </form>
  );
}
