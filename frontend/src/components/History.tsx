import { useState, useEffect } from "react"
import { Trash2, History as HistoryIcon, ChevronDown, ChevronRight, Download, Eye } from "lucide-react"
import { Button } from "@/components/ui/button"
import { fetchHistory, deleteHistory, fetchSessions, exportCsv } from "@/hooks/useApi"
import naverImg from "@/assets/naver.jpg"
import daumImg from "@/assets/daum.jpeg"
import nateImg from "@/assets/nate.png"

const PORTAL_IMGS: Record<string, string> = {
  naver: naverImg,
  daum: daumImg,
  nate: nateImg,
}

const PORTAL_LABELS: Record<string, string> = {
  naver: "네이버",
  daum: "다음",
  nate: "네이트",
}

interface HistoryItem {
  id: number
  keywords: string[] | string
  portals: string[] | string
  interval?: number
  interval_minutes?: number
  mode?: string
  created_at?: string
}

interface SessionItem {
  id: number
  history_id: number
  started_at: string
  completed_at?: string
  new_count: number
  total_count: number
  article_count: number
}

export function History({ onViewSession }: { onViewSession?: (sessionId: number, label: string) => void }) {
  const [items, setItems] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [sessions, setSessions] = useState<Record<number, SessionItem[]>>({})
  const [loadingSessions, setLoadingSessions] = useState<number | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchHistory()
      const raw = (data as { data?: HistoryItem[]; items?: HistoryItem[] }).data
        ?? (data as { items?: HistoryItem[] }).items
        ?? (data as HistoryItem[])
      setItems(Array.isArray(raw) ? raw : [])
    } catch (e) {
      setError(e instanceof Error ? e.message : "히스토리 로드 실패")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function toggleExpand(historyId: number) {
    if (expandedId === historyId) {
      setExpandedId(null)
      return
    }
    setExpandedId(historyId)
    if (!sessions[historyId]) {
      setLoadingSessions(historyId)
      try {
        const data = await fetchSessions(historyId)
        const list = Array.isArray(data) ? data : []
        setSessions((prev) => ({ ...prev, [historyId]: list as SessionItem[] }))
      } catch {
        setSessions((prev) => ({ ...prev, [historyId]: [] }))
      } finally {
        setLoadingSessions(null)
      }
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteHistory(id)
      setItems((prev) => prev.filter((i) => i.id !== id))
    } catch (e) {
      alert(e instanceof Error ? e.message : "삭제 실패")
    }
  }

  function formatKeywords(val: string[] | string | undefined): string {
    if (!val) return "-"
    if (Array.isArray(val)) return val.join(", ") || "-"
    return val || "-"
  }

  function getPortalList(val: string[] | string | undefined): string[] {
    if (!val) return []
    if (Array.isArray(val)) return val
    return val.split(",").map((s) => s.trim()).filter(Boolean)
  }

  if (loading) {
    return <div className="flex items-center justify-center h-32 text-muted-foreground">불러오는 중...</div>
  }

  if (error) {
    return <div className="flex items-center justify-center h-32 text-destructive">{error}</div>
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <HistoryIcon className="h-10 w-10 text-muted-foreground/30" />
        <p className="text-sm text-muted-foreground">키워드 검색 히스토리가 없습니다.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-lg font-bold text-foreground">키워드 검색 히스토리</h2>
      <div className="flex flex-col gap-3">
        {items.map((item, index) => {
          const portalList = getPortalList(item.portals)
          const isExpanded = expandedId === item.id
          const itemSessions = sessions[item.id] ?? []

          return (
            <div
              key={item.id}
              className="rounded-xl border border-border/50 bg-card animate-fade-up overflow-hidden"
              style={{ "--delay": `${index * 50}ms` } as React.CSSProperties}
            >
              {/* Header row */}
              <div
                className="card-hover px-4 py-3 flex items-center cursor-pointer"
                onClick={() => toggleExpand(item.id)}
              >
                {/* Expand icon */}
                <div className="mr-2 text-muted-foreground">
                  {isExpanded
                    ? <ChevronDown className="h-4 w-4" />
                    : <ChevronRight className="h-4 w-4" />}
                </div>

                {/* Left: keyword, mode, portals */}
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">
                    {formatKeywords(item.keywords)}
                  </p>
                  {item.mode && (
                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
                      {item.mode}
                    </span>
                  )}
                  <div className="flex gap-1 flex-shrink-0">
                    {portalList.map((p) =>
                      PORTAL_IMGS[p] ? (
                        <img key={p} src={PORTAL_IMGS[p]} alt={PORTAL_LABELS[p] ?? p} title={PORTAL_LABELS[p] ?? p} className="h-5 w-5 rounded object-cover" />
                      ) : null
                    )}
                  </div>
                </div>

                {/* Right: method, date, download, delete */}
                <div className="flex items-center gap-3 flex-shrink-0">
                  <span className="text-xs text-muted-foreground">
                    {item.interval_minutes ? `${item.interval_minutes}분 간격` : "즉시 수집"}
                  </span>
                  <span className="text-xs text-muted-foreground w-[150px] text-right">
                    {item.created_at ? new Date(item.created_at).toLocaleString("ko-KR") : "-"}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-muted-foreground hover:text-primary transition-colors"
                    onClick={(e) => { e.stopPropagation(); exportCsv({ history_id: item.id }) }}
                    title="전체 다운로드"
                  >
                    <Download className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-muted-foreground hover:text-destructive transition-colors"
                    onClick={(e) => { e.stopPropagation(); handleDelete(item.id) }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>

              {/* Sessions accordion */}
              {isExpanded && (
                <div className="border-t border-border/30 bg-secondary/30 px-4 py-2">
                  {loadingSessions === item.id && (
                    <p className="text-xs text-muted-foreground py-2">회차 목록 불러오는 중...</p>
                  )}
                  {loadingSessions !== item.id && itemSessions.length === 0 && (
                    <p className="text-xs text-muted-foreground py-2">수집 회차가 없습니다.</p>
                  )}
                  {itemSessions.map((session, si) => (
                    <div
                      key={session.id}
                      className="flex items-center gap-3 py-2 border-b border-border/20 last:border-b-0"
                    >
                      <span className="text-xs font-medium text-foreground w-16">
                        {si + 1}회차
                      </span>
                      <span className="text-xs text-muted-foreground">
                        신규 {session.new_count}건 / 수집 {session.total_count}건
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {session.started_at ? new Date(session.started_at).toLocaleString("ko-KR") : ""}
                      </span>
                      <div className="flex-1" />
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-muted-foreground hover:text-primary"
                        onClick={() => onViewSession?.(session.id, `${formatKeywords(item.keywords)} · ${item.mode ?? "OR"} · ${si + 1}회차`)}
                        title="기사 보기"
                      >
                        <Eye className="h-3 w-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-muted-foreground hover:text-primary"
                        onClick={() => exportCsv({ session_id: session.id })}
                        title="회차별 다운로드"
                      >
                        <Download className="h-3 w-3" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
