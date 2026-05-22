const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Municipality {
  id: string;
  province: string;
  name: string;
  root_url: string;
  active: boolean;
  pages_crawled: number;
  documents_found: number;
  last_crawled: string | null;
  changes_detected: number;
}

export interface Page {
  id: number;
  municipality_id: string;
  url: string;
  content_type: string | null;
  content_hash: string | null;
  status_code: number | null;
  depth: number;
  last_crawled: string;
}

export interface Document {
  id: number;
  municipality_id: string;
  url: string;
  file_type: string | null;
  content_hash: string | null;
  downloaded: boolean;
  first_seen: string;
  last_seen: string;
}

export interface Diff {
  id: number;
  municipality_id: string;
  url: string;
  old_hash: string | null;
  new_hash: string | null;
  detected_at: string;
}

export interface CrawlRun {
  id: number;
  started_at: string;
  finished_at: string | null;
  municipalities: number;
  pages_crawled: number;
  pages_changed: number;
  pages_new: number;
  errors: number;
}

export interface ActiveRun {
  active: boolean;
  run_id?: number;
  started_at?: string;
  municipalities_done?: number;
  municipalities_with_data?: number;
  municipalities_total?: number;
  pages_crawled?: number;
  current_municipality?: string | null;
  current_url?: string | null;
}

export interface SearchResult {
  type: string;
  municipality_id: string;
  url: string;
  file_type: string | null;
  last_seen: string | null;
  last_crawled: string | null;
}

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

export const api = {
  getMunicipalities: (province?: string) =>
    apiFetch<Municipality[]>(`/municipalities${province ? `?province=${encodeURIComponent(province)}` : ""}`),

  getMunicipality: (id: string) =>
    apiFetch<Municipality>(`/municipalities/${id}`),

  getMunicipalityPages: (id: string, limit = 100) =>
    apiFetch<Page[]>(`/municipalities/${id}/pages?limit=${limit}`),

  getMunicipalityDocuments: (id: string, limit = 100) =>
    apiFetch<Document[]>(`/municipalities/${id}/documents?limit=${limit}`),

  getMunicipalityDiffs: (id: string, limit = 50) =>
    apiFetch<Diff[]>(`/municipalities/${id}/diffs?limit=${limit}`),

  getDocuments: (fileType?: string, limit = 100) =>
    apiFetch<Document[]>(`/documents?limit=${limit}${fileType ? `&file_type=${fileType}` : ""}`),

  getRuns: () =>
    apiFetch<CrawlRun[]>("/runs"),

  getActiveRun: () =>
    fetch(`${API_BASE}/runs/active`, { cache: "no-store" })
      .then((r) => r.json() as Promise<ActiveRun>)
      .catch(() => ({ active: false }) as ActiveRun),

  search: (q: string, type?: string) =>
    apiFetch<{ total: number; results: SearchResult[] }>(
      `/search?q=${encodeURIComponent(q)}${type ? `&type=${type}` : ""}`
    ),
};
