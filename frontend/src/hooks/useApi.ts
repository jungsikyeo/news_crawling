const BASE_URL = "http://127.0.0.1:8000"

export interface NewsParams {
  keyword?: string
  portal?: string
  search?: string
  date_from?: string
  date_to?: string
  limit?: number
  offset?: number
  sort_by?: string
  sort_order?: string
  session_id?: number
  history_id?: number
}

export interface CrawlStartData {
  keywords: string[]
  portals: string[]
  interval: number
  search_from?: string
  mode?: string
}

export interface RunOnceData {
  keywords: string[]
  portals: string[]
  search_from?: string
  mode?: string
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, options)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API error ${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

export async function fetchNews(params: NewsParams = {}) {
  const query = new URLSearchParams()
  if (params.keyword) query.set("keyword", params.keyword)
  if (params.portal) query.set("portal", params.portal)
  if (params.search) query.set("search", params.search)
  if (params.date_from) query.set("date_from", params.date_from)
  if (params.date_to) query.set("date_to", params.date_to)
  if (params.limit != null) query.set("limit", String(params.limit))
  if (params.offset != null) query.set("offset", String(params.offset))
  if (params.sort_by) query.set("sort_by", params.sort_by)
  if (params.sort_order) query.set("sort_order", params.sort_order)
  if (params.session_id != null) query.set("session_id", String(params.session_id))
  if (params.history_id != null) query.set("history_id", String(params.history_id))
  const qs = query.toString()
  return apiFetch<unknown>(`/api/news${qs ? `?${qs}` : ""}`)
}

export async function fetchCrawlStatus() {
  return apiFetch<unknown>("/api/crawl/status")
}

export async function startCrawl(data: CrawlStartData) {
  return apiFetch<unknown>("/api/crawl/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      keywords: data.keywords,
      portals: data.portals,
      interval_minutes: data.interval,
      start_date: data.search_from ?? "",
      mode: data.mode ?? "OR",
    }),
  })
}

export async function stopCrawl() {
  return apiFetch<unknown>("/api/crawl/stop", { method: "POST" })
}

export async function runOnce(data: RunOnceData) {
  return apiFetch<unknown>("/api/crawl/run-once", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      keywords: data.keywords,
      portals: data.portals,
      start_date: data.search_from ?? "",
      mode: data.mode ?? "OR",
    }),
  })
}

export type StatType = "daily" | "keyword" | "portal" | "publisher" | "hourly" | "article-hourly"

export interface StatsFilter {
  date_from?: string
  date_to?: string
  keyword?: string
  portal?: string
}

export async function fetchStats(type: StatType, filter?: StatsFilter) {
  const query = new URLSearchParams()
  if (filter?.date_from) query.set("date_from", filter.date_from)
  if (filter?.date_to) query.set("date_to", filter.date_to)
  if (filter?.keyword) query.set("keyword", filter.keyword)
  if (filter?.portal) query.set("portal", filter.portal)
  const qs = query.toString()
  return apiFetch<unknown>(`/api/stats/${type}${qs ? `?${qs}` : ""}`)
}

export async function fetchHistory() {
  return apiFetch<unknown>("/api/history")
}

export async function deleteHistory(id: number | string) {
  return apiFetch<unknown>(`/api/history/${id}`, { method: "DELETE" })
}

export async function openUrl(url: string) {
  return apiFetch<unknown>("/api/news/open-url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  })
}

export async function fetchSessions(historyId: number) {
  return apiFetch<unknown>(`/api/history/${historyId}/sessions`)
}

export interface ExportParams {
  session_id?: number
  history_id?: number
  keyword?: string
  date_from?: string
  date_to?: string
}

export async function exportCsv(params: ExportParams = {}): Promise<void> {
  const query = new URLSearchParams()
  if (params.session_id != null) query.set("session_id", String(params.session_id))
  if (params.history_id != null) query.set("history_id", String(params.history_id))
  if (params.keyword) query.set("keyword", params.keyword)
  if (params.date_from) query.set("date_from", params.date_from)
  if (params.date_to) query.set("date_to", params.date_to)
  const qs = query.toString()
  const res = await fetch(`${BASE_URL}/api/news/export${qs ? `?${qs}` : ""}`)
  if (!res.ok) throw new Error(`Export failed: ${res.status}`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  const now = new Date()
  a.download = `news_export_${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}.csv`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export async function resetData() {
  return apiFetch<unknown>("/api/news/reset", { method: "DELETE" })
}

export async function toggleScrap(newsId: number) {
  return apiFetch<{ scrapped: boolean }>(`/api/news/scrap/${newsId}`, { method: "POST" })
}

export async function fetchScrapIds() {
  return apiFetch<{ scrap_ids: number[] }>("/api/news/scrap-ids")
}

export async function fetchScraps(limit = 100, offset = 0) {
  return apiFetch<unknown>(`/api/news/scraps?limit=${limit}&offset=${offset}`)
}

// === Report types ===

export interface ReportStatus {
  is_generating: boolean
  status: string
  progress_detail: string
  last_error: string | null
  last_report_path: string | null
  cli_available: boolean
  cli_message: string
}

export interface ReportFile {
  filename: string
  size: number
  created_at: string
}

// === Report functions ===

export async function generateReport(date?: string, categories?: string) {
  return apiFetch<{ status?: string; error?: string }>("/api/report/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ date: date ?? null, categories: categories || null }),
  })
}

export async function fetchReportStatus() {
  return apiFetch<ReportStatus>("/api/report/status")
}

export async function fetchReportList() {
  return apiFetch<{ reports: ReportFile[] }>("/api/report/list")
}

export async function downloadReport(filename: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/report/download/${encodeURIComponent(filename)}`)
  if (!res.ok) throw new Error(`Download failed: ${res.status}`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
