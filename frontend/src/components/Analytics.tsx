import { useState, useEffect, useCallback, useRef } from "react"
import ReactECharts from "echarts-for-react"
import { Download, BarChart2, Hash, Globe, Building2, Calendar } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { fetchStats, exportCsv } from "@/hooks/useApi"
import type { StatsFilter } from "@/hooks/useApi"

interface DailyStat {
  date: string
  keyword: string
  count: number
}
interface KeywordStat { keyword: string; count: number }
interface PortalStat { portal: string; count: number }
interface PublisherStat { publisher: string; count: number }
interface HourlyStat { hour: number; count: number }

interface AllStats {
  daily: DailyStat[]
  keyword: KeywordStat[]
  portal: PortalStat[]
  publisher: PublisherStat[]
  hourly: HourlyStat[]
  articleHourly: HourlyStat[]
}

function getAccentColor() {
  const style = getComputedStyle(document.documentElement)
  const primary = style.getPropertyValue("--primary").trim()
  if (!primary) return "#6366f1"
  const parts = primary.split(" ")
  if (parts.length === 3) {
    return `hsl(${parts[0]}, ${parts[1]}, ${parts[2]})`
  }
  return "#6366f1"
}

function getCssVar(name: string) {
  const style = getComputedStyle(document.documentElement)
  const val = style.getPropertyValue(name).trim()
  return val ? `hsl(${val})` : undefined
}

function daysAgo(n: number) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

const PRESETS = [
  { label: "오늘", from: () => todayStr(), to: () => todayStr() },
  { label: "최근 7일", from: () => daysAgo(7), to: () => todayStr() },
  { label: "최근 30일", from: () => daysAgo(30), to: () => todayStr() },
  { label: "전체", from: () => "", to: () => "" },
]

export function Analytics() {
  const [stats, setStats] = useState<AllStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)
  const [accentColor, setAccentColor] = useState("#6366f1")
  const [textColor, setTextColor] = useState("rgba(255,255,255,0.55)")
  const [gridColor, setGridColor] = useState("rgba(255,255,255,0.07)")

  // Filters
  const [dateFrom, setDateFrom] = useState(() => daysAgo(7))
  const [dateTo, setDateTo] = useState(() => todayStr())
  const [filterKeyword, setFilterKeyword] = useState("")
  const [debouncedKeyword, setDebouncedKeyword] = useState("")
  const [filterPortal, setFilterPortal] = useState("")
  const [activePreset, setActivePreset] = useState("최근 7일")
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    function update() {
      setAccentColor(getAccentColor())
      setTextColor(getCssVar("--muted-foreground") ?? "rgba(255,255,255,0.55)")
      setGridColor(getCssVar("--border") ?? "rgba(255,255,255,0.07)")
    }
    update()
    const observer = new MutationObserver(update)
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] })
    return () => observer.disconnect()
  }, [])

  // Debounce keyword input
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedKeyword(filterKeyword), 1500)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [filterKeyword])

  const loadStats = useCallback(async () => {
    setLoading(true)
    setError(null)
    const f: StatsFilter = {
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      keyword: debouncedKeyword || undefined,
      portal: filterPortal || undefined,
    }
    try {
      const [daily, keyword, portal, publisher, hourly, articleHourly] = await Promise.all([
        fetchStats("daily", f),
        fetchStats("keyword", f),
        fetchStats("portal", f),
        fetchStats("publisher", f),
        fetchStats("hourly", f),
        fetchStats("article-hourly", f),
      ])
      setStats({
        daily: (daily as { data?: DailyStat[] }).data ?? (daily as DailyStat[]),
        keyword: (keyword as { data?: KeywordStat[] }).data ?? (keyword as KeywordStat[]),
        portal: (portal as { data?: PortalStat[] }).data ?? (portal as PortalStat[]),
        publisher: (publisher as { data?: PublisherStat[] }).data ?? (publisher as PublisherStat[]),
        hourly: (hourly as { data?: HourlyStat[] }).data ?? (hourly as HourlyStat[]),
        articleHourly: (articleHourly as { data?: HourlyStat[] }).data ?? (articleHourly as HourlyStat[]),
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : "통계 로드 실패")
    } finally {
      setLoading(false)
    }
  }, [dateFrom, dateTo, debouncedKeyword, filterPortal])

  useEffect(() => {
    void loadStats()
  }, [loadStats])

  async function handleExport() {
    setExporting(true)
    try {
      await exportCsv()
    } finally {
      setExporting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        통계 불러오는 중...
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 text-destructive">
        {error}
      </div>
    )
  }

  const s = stats!

  const totalCount = s.keyword.reduce((a, b) => a + b.count, 0)
  const keywordCount = s.keyword.length
  const portalCount = s.portal.length
  const publisherCount = s.publisher.length

  const allDates = [...new Set(s.daily.map((d) => d.date))].sort()
  const allKeywords = [...new Set(s.daily.map((d) => d.keyword))]
  const dailySeries = allKeywords.map((kw, i) => ({
    name: kw,
    type: "bar" as const,
    stack: "total",
    data: allDates.map((date) => {
      const found = s.daily.find((d) => d.date === date && d.keyword === kw)
      return found?.count ?? 0
    }),
    itemStyle: { opacity: 0.7 + (i / allKeywords.length) * 0.3 },
  }))

  const tooltipStyle = {
    backgroundColor: "rgba(10,10,20,0.92)",
    borderColor: gridColor,
    textStyle: { color: textColor },
  }

  const dailyOption = {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis", ...tooltipStyle },
    legend: { data: allKeywords, textStyle: { color: textColor }, top: 0 },
    grid: { left: "3%", right: "3%", bottom: "3%", top: "40px", containLabel: true },
    xAxis: {
      type: "category",
      data: allDates,
      axisLine: { lineStyle: { color: gridColor } },
      axisLabel: { color: textColor, fontSize: 11 },
      splitLine: { lineStyle: { color: gridColor } },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: textColor, fontSize: 11 },
      splitLine: { lineStyle: { color: gridColor } },
    },
    color: [accentColor, "#818cf8", "#a78bfa", "#c084fc", "#e879f9"],
    series: dailySeries,
  }

  const donutCommon = {
    backgroundColor: "transparent",
    tooltip: { trigger: "item" as const, ...tooltipStyle },
    legend: { orient: "vertical" as const, right: "0%", top: "center", textStyle: { color: textColor, fontSize: 11 } },
  }

  const keywordDonutOption = {
    ...donutCommon,
    series: [{
      name: "키워드",
      type: "pie",
      radius: ["40%", "70%"],
      center: ["40%", "50%"],
      data: s.keyword.map((k) => ({ name: k.keyword, value: k.count })),
      label: { show: false },
      itemStyle: { borderColor: "rgba(0,0,0,0.3)", borderWidth: 2 },
      color: [accentColor, "#818cf8", "#a78bfa", "#c084fc", "#e879f9"],
    }],
  }

  const portalDonutOption = {
    ...donutCommon,
    series: [{
      name: "포털",
      type: "pie",
      radius: ["40%", "70%"],
      center: ["40%", "50%"],
      data: s.portal.map((p) => ({ name: { naver: "네이버", daum: "다음", nate: "네이트" }[p.portal] ?? p.portal, value: p.count })),
      label: { show: false },
      itemStyle: { borderColor: "rgba(0,0,0,0.3)", borderWidth: 2 },
      color: [accentColor, "#818cf8", "#a78bfa"],
    }],
  }

  const publisherOption = {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" as const, ...tooltipStyle },
    grid: { left: "3%", right: "6%", top: "3%", bottom: "3%", containLabel: true },
    xAxis: {
      type: "value" as const,
      axisLabel: { color: textColor, fontSize: 11 },
      splitLine: { lineStyle: { color: gridColor } },
    },
    yAxis: {
      type: "category" as const,
      data: s.publisher.slice(0, 15).map((p) => p.publisher).reverse(),
      axisLabel: { color: textColor, fontSize: 11 },
      axisLine: { lineStyle: { color: gridColor } },
    },
    color: [accentColor],
    series: [{
      name: "기사수",
      type: "bar" as const,
      data: s.publisher.slice(0, 15).map((p) => p.count).reverse(),
      itemStyle: { borderRadius: [0, 4, 4, 0] },
    }],
  }

  const hourlyOption = {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" as const, ...tooltipStyle },
    grid: { left: "3%", right: "3%", bottom: "3%", top: "3%", containLabel: true },
    xAxis: {
      type: "category" as const,
      data: s.hourly.map((h) => `${h.hour}시`),
      axisLine: { lineStyle: { color: gridColor } },
      axisLabel: { color: textColor, fontSize: 11 },
      splitLine: { lineStyle: { color: gridColor } },
    },
    yAxis: {
      type: "value" as const,
      axisLabel: { color: textColor, fontSize: 11 },
      splitLine: { lineStyle: { color: gridColor } },
    },
    color: [accentColor],
    series: [{
      name: "기사수",
      type: "line" as const,
      smooth: true,
      areaStyle: { opacity: 0.15 },
      data: s.hourly.map((h) => h.count),
      lineStyle: { width: 2 },
      symbol: "none",
    }],
  }

  const articleHourlyOption = {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" as const, ...tooltipStyle },
    grid: { left: "3%", right: "3%", bottom: "3%", top: "3%", containLabel: true },
    xAxis: {
      type: "category" as const,
      data: s.articleHourly.map((h) => `${h.hour}시`),
      axisLine: { lineStyle: { color: gridColor } },
      axisLabel: { color: textColor, fontSize: 11 },
      splitLine: { lineStyle: { color: gridColor } },
    },
    yAxis: {
      type: "value" as const,
      axisLabel: { color: textColor, fontSize: 11 },
      splitLine: { lineStyle: { color: gridColor } },
    },
    color: ["#f59e0b"],
    series: [{
      name: "기사수",
      type: "bar" as const,
      data: s.articleHourly.map((h) => h.count),
      itemStyle: { borderRadius: [4, 4, 0, 0], opacity: 0.85 },
    }],
  }

  const metricCards = [
    { label: "총 기사", value: totalCount, icon: BarChart2 },
    { label: "키워드", value: keywordCount, icon: Hash },
    { label: "포털", value: portalCount, icon: Globe },
    { label: "언론사", value: publisherCount, icon: Building2 },
  ]

  return (
    <div className="flex flex-col gap-6">
      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2 bg-card/50 rounded-lg p-3 border border-border/50">
        {/* Presets */}
        <div className="flex gap-1 mr-2">
          {PRESETS.map((p) => (
            <Button
              key={p.label}
              size="sm"
              variant={activePreset === p.label ? "default" : "outline"}
              className="h-7 text-xs px-3"
              onClick={() => {
                setDateFrom(p.from())
                setDateTo(p.to())
                setActivePreset(p.label)
              }}
            >
              {p.label}
            </Button>
          ))}
        </div>

        <div className="flex items-center gap-1.5">
          <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setActivePreset("") }}
            className="h-7 text-xs bg-secondary border-border w-[130px]"
          />
          <span className="text-muted-foreground text-xs">~</span>
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setActivePreset("") }}
            className="h-7 text-xs bg-secondary border-border w-[130px]"
          />
        </div>

        <Input
          placeholder="키워드 필터"
          value={filterKeyword}
          onChange={(e) => setFilterKeyword(e.target.value)}
          className="h-7 text-xs bg-secondary border-border w-[120px]"
        />

        <select
          value={filterPortal}
          onChange={(e) => setFilterPortal(e.target.value)}
          className="h-7 rounded-md border border-border bg-secondary px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">전체 포털</option>
          <option value="naver">네이버</option>
          <option value="daum">다음</option>
          <option value="nate">네이트</option>
        </select>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-4 gap-4">
        {metricCards.map(({ label, value, icon: Icon }, i) => (
          <div
            key={label}
            className="rounded-xl border border-border/50 bg-card p-5 card-hover animate-fade-up"
            style={{ "--delay": `${i * 60}ms` } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
              <Icon className="h-3.5 w-3.5" />
              <span className="text-[11px] uppercase tracking-wider">{label}</span>
            </div>
            <p className="text-3xl font-bold text-foreground">{value.toLocaleString()}</p>
          </div>
        ))}
      </div>

      {/* Daily bar chart */}
      <div className="rounded-xl border border-border/50 bg-card p-4">
        <h3 className="text-sm font-medium text-foreground mb-3">일별 수집량</h3>
        <ReactECharts option={dailyOption} style={{ height: 240 }} />
      </div>

      {/* Donut charts */}
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-xl border border-border/50 bg-card p-4">
          <h3 className="text-sm font-medium text-foreground mb-3">키워드별 비율</h3>
          <ReactECharts option={keywordDonutOption} style={{ height: 200 }} />
        </div>
        <div className="rounded-xl border border-border/50 bg-card p-4">
          <h3 className="text-sm font-medium text-foreground mb-3">포털별 비율</h3>
          <ReactECharts option={portalDonutOption} style={{ height: 200 }} />
        </div>
      </div>

      {/* Publisher horizontal bar */}
      <div className="rounded-xl border border-border/50 bg-card p-4">
        <h3 className="text-sm font-medium text-foreground mb-3">언론사 Top 15</h3>
        <ReactECharts option={publisherOption} style={{ height: 320 }} />
      </div>

      {/* Hourly area chart */}
      <div className="rounded-xl border border-border/50 bg-card p-4">
        <h3 className="text-sm font-medium text-foreground mb-3">시간대별 수집량</h3>
        <ReactECharts option={hourlyOption} style={{ height: 200 }} />
      </div>

      {/* Article hourly bar chart */}
      <div className="rounded-xl border border-border/50 bg-card p-4">
        <h3 className="text-sm font-medium text-foreground mb-3">시간대별 기사량 (게시 시간 기준)</h3>
        <ReactECharts option={articleHourlyOption} style={{ height: 200 }} />
      </div>

      {/* CSV export */}
      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={handleExport} disabled={exporting}>
          <Download className="h-3.5 w-3.5 mr-1.5" />
          {exporting ? "내보내는 중..." : "CSV 내보내기"}
        </Button>
      </div>
    </div>
  )
}
