import { useState, useEffect, useCallback, useRef } from "react"
import type { MutableRefObject } from "react"
import { ExternalLink, Newspaper, Search, Star } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { fetchNews, toggleScrap, fetchScrapIds } from "@/hooks/useApi"
import { highlightText } from "@/lib/highlight"
import naverImg from "@/assets/naver.jpg"
import daumImg from "@/assets/daum.jpeg"
import nateImg from "@/assets/nate.png"

const PORTAL_IMGS: Record<string, string> = {
  naver: naverImg,
  daum: daumImg,
  nate: nateImg,
}
const PORTAL_NAMES: Record<string, string> = {
  naver: "네이버",
  daum: "다음",
  nate: "네이트",
}

interface NewsArticle {
  id: number
  title: string
  url: string
  description?: string
  publisher?: string
  published_at?: string
  keyword?: string
  portal?: string
  portals?: string
}

const PAGE_SIZE = 20

export function NewsList({ refreshRef }: { refreshRef?: MutableRefObject<(() => void) | null> }) {
  const [articles, setArticles] = useState<NewsArticle[]>([])
  const [keyword, setKeyword] = useState("")
  const [portal, setPortal] = useState("")
  const [searchText, setSearchText] = useState("")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [loading, setLoading] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [scrapIds, setScrapIds] = useState<Set<number>>(new Set())
  const offsetRef = useRef(0)
  const loadingRef = useRef(false)
  const sentinelRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const loadArticles = useCallback(async (reset: boolean) => {
    if (loadingRef.current) return
    loadingRef.current = true
    setLoading(true)
    setError(null)
    try {
      const offset = reset ? 0 : offsetRef.current
      const data = await fetchNews({
        keyword: keyword || undefined,
        portal: portal || undefined,
        search: searchText || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        limit: PAGE_SIZE,
        offset,
      })
      const result = data as { items?: NewsArticle[] }
      const items = result.items ?? []
      if (reset) {
        setArticles(items)
        offsetRef.current = items.length
      } else {
        setArticles((prev) => [...prev, ...items])
        offsetRef.current += items.length
      }
      setHasMore(items.length >= PAGE_SIZE)
    } catch (e) {
      setError(e instanceof Error ? e.message : "오류 발생")
    } finally {
      loadingRef.current = false
      setLoading(false)
    }
  }, [keyword, portal, searchText, dateFrom, dateTo])

  // Load scrap ids
  useEffect(() => {
    fetchScrapIds().then((data) => setScrapIds(new Set(data.scrap_ids))).catch(() => {})
  }, [])

  async function handleToggleScrap(newsId: number) {
    try {
      const result = await toggleScrap(newsId)
      setScrapIds((prev) => {
        const next = new Set(prev)
        if (result.scrapped) next.add(newsId)
        else next.delete(newsId)
        return next
      })
    } catch { /* silent */ }
  }

  // Initial load
  useEffect(() => {
    offsetRef.current = 0
    setArticles([])
    setHasMore(true)
    loadArticles(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keyword, portal, searchText, dateFrom, dateTo])

  // Expose refresh function via ref
  useEffect(() => {
    if (refreshRef) refreshRef.current = () => loadArticles(true)
  })

  // Infinite scroll with IntersectionObserver
  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loadingRef.current) {
          loadArticles(false)
        }
      },
      { threshold: 0.1 }
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [hasMore, loadArticles])

  function handleSearch() {
    offsetRef.current = 0
    setArticles([])
    loadArticles(true)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Filter bar */}
      <div className="flex flex-wrap gap-2 mb-4 bg-card/50 rounded-lg p-3 border border-border/50">
        <div className="relative flex-1 min-w-[160px]">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="제목, 내용 검색..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="h-8 text-sm bg-secondary border-border pl-8"
          />
        </div>
        <Input
          placeholder="키워드 필터"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          className="h-8 text-sm bg-secondary border-border w-[140px]"
        />
        <select
          value={portal}
          onChange={(e) => setPortal(e.target.value)}
          className="h-8 rounded-md border border-border bg-secondary px-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">전체 포털</option>
          <option value="naver">네이버</option>
          <option value="daum">다음</option>
          <option value="nate">네이트</option>
        </select>
        <Input
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          className="h-8 text-sm bg-secondary border-border w-[140px]"
          title="시작일"
        />
        <span className="flex items-center text-muted-foreground text-xs">~</span>
        <Input
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          className="h-8 text-sm bg-secondary border-border w-[140px]"
          title="종료일"
        />
      </div>

      {/* Error */}
      {error && (
        <p className="text-sm text-destructive py-4">{error}</p>
      )}

      {/* Empty state */}
      {!loading && !error && articles.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <Newspaper className="h-10 w-10 text-muted-foreground/30" />
          <p className="text-sm text-muted-foreground">뉴스 기사가 없습니다.</p>
        </div>
      )}

      {/* Article list */}
      <div ref={containerRef} className="flex flex-col gap-3 overflow-y-auto flex-1 pr-1">
        {articles.map((article, index) => {
          const portalList = article.portals ? article.portals.split(",") : (article.portal ? [article.portal] : [])
          return (
            <article
              key={`${article.id}-${index}`}
              className={[
                "card-hover rounded-xl border bg-card p-4 animate-fade-up",
                scrapIds.has(article.id)
                  ? "border-l-[3px] border-l-primary border-border/50"
                  : "border-border/50",
              ].join(" ")}
              style={{ "--delay": `${Math.min(index, 10) * 40}ms` } as React.CSSProperties}
            >
              <div className="flex items-start gap-3 relative">
                {/* Scrap button */}
                <button
                  onClick={() => handleToggleScrap(article.id)}
                  className={[
                    "absolute -top-1 -right-1 p-1.5 rounded-lg transition-all",
                    scrapIds.has(article.id)
                      ? "text-amber-400"
                      : "text-muted-foreground/20 hover:text-amber-400/60",
                  ].join(" ")}
                  title={scrapIds.has(article.id) ? "스크랩 해제" : "스크랩"}
                >
                  <Star className={`h-5 w-5 ${scrapIds.has(article.id) ? "fill-amber-400" : ""}`} />
                </button>

                {/* Portal icons - vertical stack */}
                <div className="flex flex-col gap-1 flex-shrink-0 mt-0.5">
                  {portalList.map((p) => (
                    PORTAL_IMGS[p.trim()] && (
                      <img
                        key={p}
                        src={PORTAL_IMGS[p.trim()]}
                        alt={PORTAL_NAMES[p.trim()] || p}
                        title={PORTAL_NAMES[p.trim()] || p}
                        className="h-4 w-4 rounded object-cover"
                      />
                    )
                  ))}
                </div>

                <div className="flex-1 min-w-0">
                  {/* Badges */}
                  <div className="flex flex-wrap gap-1.5 mb-1.5">
                    {article.keyword && (
                      <Badge className="text-[10px] h-4 px-1.5 bg-primary/10 text-primary border border-primary/20 rounded-md">
                        {article.keyword}
                      </Badge>
                    )}
                  </div>

                  {/* Title */}
                  <a
                    href={article.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group flex items-start gap-1 text-sm font-medium text-foreground hover:text-primary transition-colors mb-1"
                  >
                    <span className="line-clamp-2">
                      {highlightText(article.title, [
                        { term: article.keyword ?? "", styleKey: "keyword" },
                        { term: searchText, styleKey: "search" },
                      ])}
                    </span>
                    <ExternalLink className="h-3 w-3 flex-shrink-0 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </a>

                  {/* Description */}
                  {article.description && (
                    <p className="text-xs text-muted-foreground mb-2">
                      {highlightText(
                        article.description.slice(0, 250) + (article.description.length > 250 ? "..." : ""),
                        [
                          { term: article.keyword ?? "", styleKey: "keyword" },
                          { term: searchText, styleKey: "search" },
                        ]
                      )}
                    </p>
                  )}

                  {/* Meta */}
                  <div className="flex gap-3 text-[11px] text-muted-foreground">
                    {article.publisher && <span>{article.publisher}</span>}
                    {article.published_at && <span>{article.published_at}</span>}
                  </div>
                </div>
              </div>
            </article>
          )
        })}

        {/* Infinite scroll sentinel */}
        <div ref={sentinelRef} className="h-8 flex items-center justify-center">
          {loading && (
            <p className="text-xs text-muted-foreground">불러오는 중...</p>
          )}
          {!hasMore && articles.length > 0 && (
            <p className="text-xs text-muted-foreground">모든 기사를 불러왔습니다.</p>
          )}
        </div>
      </div>
    </div>
  )
}
