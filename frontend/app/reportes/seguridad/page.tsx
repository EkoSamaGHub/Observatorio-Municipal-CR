import { getTranslations } from "next-intl/server";
import { api, DomainExpiry, SSLReport } from "@/lib/api";

const GRADE_STYLE: Record<string, string> = {
  "A+": "bg-green-100 text-green-800",
  "A":  "bg-green-100 text-green-800",
  "B":  "bg-yellow-100 text-yellow-800",
  "C":  "bg-orange-100 text-orange-800",
  "D":  "bg-orange-100 text-orange-800",
  "F":  "bg-red-100 text-red-800",
  "T":  "bg-red-100 text-red-800",
  "M":  "bg-red-100 text-red-800",
};

function GradeBadge({ grade }: { grade: string | null }) {
  if (!grade) {
    return <span className="text-xs font-mono bg-gray-100 text-gray-400 px-2 py-0.5 rounded">—</span>;
  }
  const cls = GRADE_STYLE[grade] ?? "bg-gray-100 text-gray-600";
  return (
    <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${cls}`}>
      {grade}
    </span>
  );
}

function ExpiryCell({ dateStr }: { dateStr: string | null }) {
  if (!dateStr) {
    return <span className="text-gray-400">—</span>;
  }
  const date = new Date(dateStr);
  const daysLeft = Math.floor((date.getTime() - Date.now()) / 86_400_000);
  const label = date.toLocaleDateString("es-CR");

  if (daysLeft < 0) {
    return <span className="text-red-700 font-semibold">{label} ⚠</span>;
  }
  if (daysLeft < 30) {
    return <span className="text-red-600 font-medium">{label} ({daysLeft}d)</span>;
  }
  if (daysLeft < 90) {
    return <span className="text-orange-600">{label} ({daysLeft}d)</span>;
  }
  return <span className="text-green-700">{label}</span>;
}

interface MergedRow {
  municipality_id: string;
  municipality_name: string;
  province: string;
  domain: string;
  ssl: SSLReport | null;
  domain_rec: DomainExpiry | null;
}

export default async function SeguridadPage() {
  const t = await getTranslations("reportes");

  let sslReports: SSLReport[] = [];
  let domainExpiry: DomainExpiry[] = [];
  try {
    [sslReports, domainExpiry] = await Promise.all([
      api.getSSLReports(),
      api.getDomainExpiry(),
    ]);
  } catch {
    // API not reachable
  }

  // Merge by municipality_id — build from SSL first, then add any domain-only records
  const map = new Map<string, MergedRow>();

  for (const s of sslReports) {
    map.set(s.municipality_id, {
      municipality_id: s.municipality_id,
      municipality_name: s.municipality_name,
      province: s.province,
      domain: s.domain,
      ssl: s,
      domain_rec: null,
    });
  }

  for (const d of domainExpiry) {
    const existing = map.get(d.municipality_id);
    if (existing) {
      existing.domain_rec = d;
    } else {
      map.set(d.municipality_id, {
        municipality_id: d.municipality_id,
        municipality_name: d.municipality_name,
        province: d.province,
        domain: d.domain,
        ssl: null,
        domain_rec: d,
      });
    }
  }

  const rows = Array.from(map.values()).sort((a, b) =>
    a.province.localeCompare(b.province, "es") || a.municipality_name.localeCompare(b.municipality_name, "es")
  );

  const isEmpty = sslReports.length === 0 && domainExpiry.length === 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">{t("titulo")}</h1>
        <p className="text-gray-500 mt-1">{t("subtitulo")}</p>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded bg-green-100 border border-green-300" /> SSL A / A+
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded bg-yellow-100 border border-yellow-300" /> SSL B
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded bg-orange-100 border border-orange-300" /> SSL C / D
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded bg-red-100 border border-red-300" /> SSL F / Error
        </span>
        <span className="text-gray-400">·</span>
        <span>Vencimiento: <span className="text-red-600">rojo &lt;30d</span>, <span className="text-orange-600">naranja &lt;90d</span>, <span className="text-green-700">verde &gt;90d</span></span>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        {isEmpty ? (
          <div className="text-center py-16 text-gray-400 text-sm px-6">
            {t("sin_datos")}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{t("municipalidad")}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600 hidden md:table-cell">{t("provincia")}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600 hidden lg:table-cell">{t("dominio")}</th>
                <th className="text-center px-4 py-3 font-medium text-gray-600">{t("grado_ssl")}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600 hidden sm:table-cell">{t("vence_cert")}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600 hidden sm:table-cell">{t("vence_dominio")}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600 hidden xl:table-cell">{t("revisado")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((row) => (
                <tr key={row.municipality_id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {row.municipality_name}
                    {row.ssl?.has_warnings && (
                      <span className="ml-1.5 text-xs text-orange-500" title={t("advertencia")}>⚠</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-500 hidden md:table-cell">{row.province}</td>
                  <td className="px-4 py-3 text-gray-400 text-xs hidden lg:table-cell">
                    <a
                      href={`https://${row.domain}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-blue-600 transition-colors"
                    >
                      {row.domain}
                    </a>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <GradeBadge grade={row.ssl?.grade ?? null} />
                  </td>
                  <td className="px-4 py-3 text-xs hidden sm:table-cell">
                    <ExpiryCell dateStr={row.ssl?.cert_expiry ?? null} />
                  </td>
                  <td className="px-4 py-3 text-xs hidden sm:table-cell">
                    <ExpiryCell dateStr={row.domain_rec?.expiry_date ?? null} />
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs hidden xl:table-cell">
                    {row.ssl?.checked_at
                      ? new Date(row.ssl.checked_at).toLocaleDateString("es-CR")
                      : row.domain_rec?.checked_at
                      ? new Date(row.domain_rec.checked_at).toLocaleDateString("es-CR")
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
