"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

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
    if (q) params.set("q", q);
    if (tipo) params.set("tipo", tipo);
    router.push(`/busqueda?${params.toString()}`);
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 flex-wrap">
      <input
        type="text"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={t("placeholder")}
        className="flex-1 min-w-48 border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      <select
        value={tipo}
        onChange={(e) => setTipo(e.target.value)}
        className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        <option value="">{t("todos")}</option>
        <option value="page">{t("tipo_pagina")}</option>
        <option value="document">{t("tipo_documento")}</option>
      </select>
      <button
        type="submit"
        className="bg-blue-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
      >
        {t("titulo")}
      </button>
    </form>
  );
}
