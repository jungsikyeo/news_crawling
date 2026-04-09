import { useState, useEffect } from "react"
import { ExternalLink, Star, StarOff } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { fetchScraps, toggleScrap } from "@/hooks/useApi"
import { highlightText } from "@/lib/highlight"
import naverImg from "@/assets/naver.jpg"
import daumImg from "@/assets/daum.jpeg"
import nateImg from "@/assets/nate.png"

const PORTAL_IMGS: Record<string, string> = { naver: naverImg, daum: daumImg, nate: nateImg }
const PORTAL_NAMES: Record<string, string> = { naver: "네이버", daum: "다음", nate: "네이트" }

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

export function Scraps() {
  const [articles, setArticles] = useState<NewsArticle[]>([])
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    try {
      const data = await fetchScraps()
      const result = data as { items?: NewsArticle[] }
      setArticles(result.items ?? [])
    } catch { /* silent */ }
    finally { setLoading(false) }
  }

  useEffect(() => { void load() }, [])

  async function handleRemoveScrap(newsId: number) {
    await toggleScrap(newsId)
    setArticles((prev) => prev.filter((a) => a.id !== newsId))
  }

  if (loading) {
    return <div className="flex items-center justify-center h-32 text-muted-foreground">불러오는 중...</div>
  }

  if (articles.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <Star className="h-10 w-10 text-muted-foreground/30" />
        <p className="text-sm text-muted-foreground">스크랩한 기사가 없습니다.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted-foreground">{articles.length}건 스크랩</p>
      {articles.map((article, index) => {
        const portalList = article.portals ? article.portals.split(",") : (article.portal ? [article.portal] : [])
        return (
          <article
            key={article.id}
            className="card-hover rounded-xl border border-border/50 bg-card p-4 animate-fade-up relative"
            style={{ "--delay": `${Math.min(index, 10) * 40}ms` } as React.CSSProperties}
          >
            <button
              onClick={() => handleRemoveScrap(article.id)}
              className="absolute top-3 right-3 p-1.5 rounded-lg text-amber-400 hover:text-destructive transition-colors"
              title="스크랩 해제"
            >
              <StarOff className="h-5 w-5" />
            </button>

            <div className="flex items-start gap-3">
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

              <div className="flex-1 min-w-0 pr-6">
                <div className="flex flex-wrap gap-1.5 mb-1.5">
                  {article.keyword && (
                    <Badge className="text-[10px] h-4 px-1.5 bg-primary/10 text-primary border border-primary/20 rounded-md">
                      {article.keyword}
                    </Badge>
                  )}
                </div>

                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex items-start gap-1 text-sm font-medium text-foreground hover:text-primary transition-colors mb-1"
                >
                  <span className="line-clamp-2">
                      {highlightText(article.title, [
                        { term: article.keyword ?? "", styleKey: "keyword" },
                      ])}
                    </span>
                  <ExternalLink className="h-3 w-3 flex-shrink-0 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                </a>

                {article.description && (
                  <p className="text-xs text-muted-foreground mb-2">
                    {highlightText(
                      article.description.slice(0, 250) + (article.description.length > 250 ? "..." : ""),
                      [{ term: article.keyword ?? "", styleKey: "keyword" }]
                    )}
                  </p>
                )}

                <div className="flex gap-3 text-[11px] text-muted-foreground">
                  {article.publisher && <span>{article.publisher}</span>}
                  {article.published_at && <span>{article.published_at}</span>}
                </div>
              </div>
            </div>
          </article>
        )
      })}
    </div>
  )
}
