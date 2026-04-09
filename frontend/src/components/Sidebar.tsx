import { useState } from "react"
import { Plus, X, Play, Square, Zap, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import naverImg from "@/assets/naver.jpg"
import daumImg from "@/assets/daum.jpeg"
import nateImg from "@/assets/nate.png"

const PORTALS = [
  { id: "naver", label: "네이버", img: naverImg },
  { id: "daum", label: "다음", img: daumImg },
  { id: "nate", label: "네이트", img: nateImg },
] as const

const INTERVALS = [
  { value: 15, label: "15분" },
  { value: 30, label: "30분" },
  { value: 60, label: "1시간" },
  { value: 120, label: "2시간" },
  { value: 360, label: "6시간" },
  { value: 720, label: "12시간" },
  { value: 1440, label: "24시간" },
]

function todayString() {
  return new Date().toISOString().slice(0, 10)
}

export interface SidebarStatus {
  running: boolean
  last_run?: string
  collected?: number
  new_count?: number
}

interface SidebarProps {
  status: SidebarStatus
  onStartCrawl: (data: {
    keywords: string[]
    portals: string[]
    interval: number
    search_from: string
  }) => void
  onStopCrawl: () => void
  onRunOnce: (data: {
    keywords: string[]
    portals: string[]
    search_from: string
  }) => void
  onWarning?: (message: string) => void
  onReset?: () => void
}

export function Sidebar({ status, onStartCrawl, onStopCrawl, onRunOnce, onWarning, onReset }: SidebarProps) {
  const [keywords, setKeywords] = useState<string[]>([])
  const [keywordInput, setKeywordInput] = useState("")
  const [portals, setPortals] = useState<string[]>(["naver", "daum", "nate"])
  const [searchFrom, setSearchFrom] = useState(todayString())
  const [interval, setInterval] = useState(15)

  function addKeyword() {
    const kw = keywordInput.trim()
    if (kw && !keywords.includes(kw)) {
      setKeywords((prev) => [...prev, kw])
    }
    setKeywordInput("")
  }

  function removeKeyword(kw: string) {
    setKeywords((prev) => prev.filter((k) => k !== kw))
  }

  function togglePortal(id: string) {
    setPortals((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    )
  }

  function validate(): boolean {
    if (keywords.length === 0) { onWarning?.("키워드를 1개 이상 추가하세요."); return false }
    if (portals.length === 0) { onWarning?.("포탈을 1개 이상 선택하세요."); return false }
    return true
  }

  function handleStart() {
    if (!validate()) return
    onStartCrawl({ keywords, portals, interval, search_from: searchFrom })
  }

  function handleRunOnce() {
    if (!validate()) return
    onRunOnce({ keywords, portals, search_from: searchFrom })
  }

  return (
    <aside className="w-72 flex-shrink-0 h-screen flex flex-col border-r border-border/50 glass overflow-y-auto">
      {/* Logo */}
      <div className="p-5 border-b border-border/50">
        <h1 className="text-2xl font-black tracking-tight text-foreground leading-none">
          NEWS<span className="text-primary">DESK</span>
        </h1>
        <p className="text-[10px] text-muted-foreground mt-1.5 tracking-[0.2em] uppercase">
          뉴스 크롤러 대시보드
        </p>
      </div>

      <div className="flex flex-col space-y-6 p-4 flex-1">
        {/* Keywords */}
        <section>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            키워드
          </p>
          <div className="flex gap-1.5 mb-2">
            <Input
              value={keywordInput}
              onChange={(e) => setKeywordInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addKeyword()}
              placeholder="키워드 입력..."
              className="h-8 text-xs bg-secondary border-border"
            />
            <Button size="icon" onClick={addKeyword} className="h-8 w-8 flex-shrink-0">
              <Plus className="h-3.5 w-3.5" />
            </Button>
          </div>
          <div className="flex flex-wrap gap-1.5 min-h-[24px]">
            {keywords.map((kw, i) => (
              <Badge
                key={kw}
                variant="secondary"
                className="gap-1 pr-1 animate-fade-up"
                style={{ "--delay": `${i * 40}ms` } as React.CSSProperties}
              >
                {kw}
                <button
                  onClick={() => removeKeyword(kw)}
                  className="ml-0.5 hover:text-destructive transition-colors"
                >
                  <X className="h-2.5 w-2.5" />
                </button>
              </Badge>
            ))}
            {keywords.length === 0 && (
              <p className="text-xs text-muted-foreground">
                키워드를 추가하세요
              </p>
            )}
          </div>
        </section>

        {/* Portals */}
        <section>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            포털
          </p>
          <div className="flex gap-4">
            {PORTALS.map(({ id, label, img }) => {
              const selected = portals.includes(id)
              return (
                <button
                  key={id}
                  onClick={() => togglePortal(id)}
                  title={label}
                  className="flex flex-col items-center gap-1.5 transition-all"
                >
                  <div
                    className={[
                      "w-11 h-11 rounded-xl overflow-hidden transition-all",
                      selected
                        ? "ring-2 ring-primary shadow-[0_0_12px_hsl(var(--primary)/0.3)] opacity-100"
                        : "opacity-25 grayscale",
                    ].join(" ")}
                  >
                    <img src={img} alt={label} className="h-full w-full object-cover" />
                  </div>
                  <span className="text-[10px] text-muted-foreground">{label}</span>
                </button>
              )
            })}
          </div>
        </section>

        {/* Search From */}
        <section>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            검색 시작일
          </p>
          <input
            type="date"
            value={searchFrom}
            onChange={(e) => setSearchFrom(e.target.value)}
            className="w-full h-8 rounded-md border border-border bg-secondary px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </section>

        {/* Interval */}
        <section>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            수집 간격
          </p>
          <select
            value={interval}
            onChange={(e) => setInterval(Number(e.target.value))}
            className="w-full h-8 rounded-md border border-border bg-secondary px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {INTERVALS.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </section>

        {/* Actions */}
        <section className="flex flex-col gap-2">
          <div className="flex gap-2">
            <Button
              className={[
                "flex-1 h-9 text-xs",
                !status.running ? "shadow-[0_0_16px_hsl(var(--primary)/0.25)]" : "",
              ].join(" ")}
              onClick={handleStart}
              disabled={status.running}
            >
              <Play className="h-3.5 w-3.5 mr-1" />
              시작
            </Button>
            <Button
              variant={status.running ? "destructive" : "outline"}
              className={[
                "flex-1 h-9 text-xs",
                status.running ? "shadow-[0_0_16px_rgba(239,68,68,0.3)]" : "",
              ].join(" ")}
              onClick={onStopCrawl}
              disabled={!status.running}
            >
              <Square className="h-3.5 w-3.5 mr-1" />
              중지
            </Button>
          </div>
          <Button
            variant="secondary"
            className="w-full h-9 text-xs"
            onClick={handleRunOnce}
          >
            <Zap className="h-3.5 w-3.5 mr-1" />
            즉시 수집
          </Button>
        </section>

        {/* Status */}
        <section className="border-t border-border/50 pt-4">
          <div className={[
            "flex items-center gap-2.5 mb-2 px-3 py-2 rounded-lg border",
            status.running
              ? "bg-green-500/5 border-green-500/20"
              : "bg-amber-500/5 border-amber-500/20",
          ].join(" ")}>
            <span
              className={[
                "h-2.5 w-2.5 rounded-full flex-shrink-0",
                status.running
                  ? "bg-green-500 animate-pulse shadow-[0_0_8px_#22c55e]"
                  : "bg-amber-400 shadow-[0_0_6px_#fbbf24]",
              ].join(" ")}
            />
            <span className={[
              "text-xs font-semibold",
              status.running ? "text-green-400" : "text-amber-400",
            ].join(" ")}>
              {status.running ? "수집 진행중" : "대기중"}
            </span>
          </div>
          {status.last_run && (
            <div className="text-xs text-muted-foreground space-y-0.5">
              <p>마지막 실행: {new Date(status.last_run).toLocaleString("ko-KR")}</p>
              {status.collected != null && (
                <p>
                  수집: {status.collected}건 / 신규: {status.new_count ?? 0}건
                </p>
              )}
            </div>
          )}
        </section>

        {/* Reset */}
        <div className="mt-auto pt-4">
          <Button
            variant="ghost"
            className="w-full h-8 text-xs text-destructive/70 hover:text-destructive hover:bg-destructive/10"
            onClick={onReset}
          >
            <Trash2 className="h-3 w-3 mr-1.5" />
            데이터 초기화
          </Button>
        </div>
      </div>

    </aside>
  )
}
