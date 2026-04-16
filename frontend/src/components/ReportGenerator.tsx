import { useState, useEffect, useCallback } from "react"
import { FileText, Download, Loader2, AlertCircle, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  generateReport,
  fetchReportStatus,
  fetchReportList,
  downloadReport,
  type ReportStatus,
  type ReportFile,
} from "@/hooks/useApi"

const STATUS_LABELS: Record<string, string> = {
  idle: "대기",
  fetching_articles: "기사 조회 중",
  scraping_content: "기사 본문 크롤링 중",
  ai_classifying: "AI 카테고리 분류 중",
  ai_summarizing: "AI 요약 생성 중",
  generating_hwp: "HWP 파일 생성 중",
  completed: "완료",
  error: "오류",
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function todayString(): string {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, "0")
  const d = String(now.getDate()).padStart(2, "0")
  return `${y}-${m}-${d}`
}

export default function ReportGenerator() {
  const [date, setDate] = useState(todayString)
  const [categories, setCategories] = useState("")
  const [status, setStatus] = useState<ReportStatus | null>(null)
  const [reports, setReports] = useState<ReportFile[]>([])
  const [polling, setPolling] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const loadStatus = useCallback(async () => {
    try {
      const s = await fetchReportStatus()
      setStatus(s)
      if (s.is_generating && !polling) {
        setPolling(true)
      }
      if (!s.is_generating && polling) {
        setPolling(false)
        loadReports()
        if (s.status === "completed") {
          setSuccessMsg("보고서 생성이 완료되었습니다.")
          setTimeout(() => setSuccessMsg(null), 5000)
        }
        if (s.last_error) {
          setError(s.last_error)
        }
      }
    } catch {
      // silent
    }
  }, [polling])

  const loadReports = useCallback(async () => {
    try {
      const data = await fetchReportList()
      setReports(data.reports ?? [])
    } catch {
      // silent
    }
  }, [])

  useEffect(() => {
    void loadStatus()
    void loadReports()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!polling) return
    const id = setInterval(() => {
      void loadStatus()
    }, 2000)
    return () => clearInterval(id)
  }, [polling, loadStatus])

  async function handleGenerate() {
    setError(null)
    setSuccessMsg(null)
    try {
      const res = await generateReport(date || undefined, categories || undefined)
      if (res.error) {
        setError(res.error)
        return
      }
      setPolling(true)
      void loadStatus()
    } catch (e) {
      setError(e instanceof Error ? e.message : "보고서 생성 요청에 실패했습니다.")
    }
  }

  async function handleDownload(filename: string) {
    try {
      await downloadReport(filename)
    } catch (e) {
      setError(e instanceof Error ? e.message : "다운로드에 실패했습니다.")
    }
  }

  const isGenerating = status?.is_generating ?? false
  const cliAvailable = status?.cli_available ?? true

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      {/* CLI unavailable warning */}
      {status && !cliAvailable && (
        <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
          <AlertCircle className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
          <div className="text-sm space-y-2">
            <p className="font-medium text-amber-500">AI 보고서 생성을 위해 Claude Code CLI가 필요합니다</p>
            <p className="text-muted-foreground">
              보고서 생성 기능은 Claude Code CLI를 사용하여 기사를 분류하고 요약합니다.
              아래 단계를 따라 설치해주세요.
            </p>
            <ol className="text-muted-foreground list-decimal list-inside space-y-1">
              <li>
                터미널에서 설치:{" "}
                <code className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono">
                  npm install -g @anthropic-ai/claude-code
                </code>
              </li>
              <li>
                로그인:{" "}
                <code className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono">
                  claude login
                </code>
              </li>
              <li>앱을 재시작하세요</li>
            </ol>
            <p className="text-muted-foreground text-xs">
              Claude Desktop과는 별도 설치이며,{" "}
              <a
                href="https://docs.anthropic.com/en/docs/claude-code"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline hover:no-underline"
              >
                공식 문서
              </a>
              에서 자세한 내용을 확인할 수 있습니다.
            </p>
          </div>
        </div>
      )}

      {/* Generate section */}
      <div className="rounded-xl border border-border/50 bg-card p-5">
        <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
          <FileText className="h-4 w-4 text-primary" />
          보고서 생성
        </h3>

        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-[140px_1fr_auto] gap-3 items-end">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs text-muted-foreground">날짜</label>
              <Input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                disabled={isGenerating}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs text-muted-foreground">
                카테고리 <span className="text-muted-foreground/60">· 비우면 AI 자동 분류</span>
              </label>
              <Input
                type="text"
                value={categories}
                onChange={(e) => setCategories(e.target.value)}
                placeholder="예: 경제, 외교안보, 사회"
                disabled={isGenerating}
              />
            </div>
            <Button
              onClick={handleGenerate}
              disabled={isGenerating || !cliAvailable}
              className="flex items-center gap-2"
            >
              {isGenerating ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FileText className="h-4 w-4" />
              )}
              보고서 생성
            </Button>
          </div>
        </div>

        {/* Progress display */}
        {isGenerating && status && (
          <div className="mt-4 flex items-center gap-3 rounded-lg bg-muted p-3">
            <Loader2 className="h-4 w-4 animate-spin text-primary flex-shrink-0" />
            <div className="text-sm">
              <span className="font-medium text-foreground">
                {STATUS_LABELS[status.status] ?? status.status}
              </span>
              {status.progress_detail && (
                <span className="text-muted-foreground ml-2">{status.progress_detail}</span>
              )}
            </div>
          </div>
        )}

        {/* Success message */}
        {successMsg && (
          <div className="mt-4 rounded-lg bg-emerald-500/10 border border-emerald-500/30 p-3 text-sm text-emerald-500">
            {successMsg}
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="mt-4 flex items-start gap-2 rounded-lg bg-destructive/10 border border-destructive/30 p-3">
            <AlertCircle className="h-4 w-4 text-destructive flex-shrink-0 mt-0.5" />
            <span className="text-sm text-destructive">{error}</span>
          </div>
        )}
      </div>

      {/* Report list */}
      <div className="rounded-xl border border-border/50 bg-card p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <FileText className="h-4 w-4 text-primary" />
            생성된 보고서
          </h3>
          <Button variant="ghost" size="sm" onClick={loadReports} className="h-7 px-2">
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        </div>

        {reports.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 gap-3">
            <FileText className="h-10 w-10 text-muted-foreground/30" />
            <p className="text-sm text-muted-foreground">생성된 보고서가 없습니다.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {reports.map((report) => (
              <div
                key={report.filename}
                className="flex items-center justify-between rounded-lg border border-border/50 bg-muted/50 px-4 py-3"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{report.filename}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatFileSize(report.size)} &middot; {report.created_at}
                    </p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDownload(report.filename)}
                  className="flex-shrink-0 h-8 px-3"
                >
                  <Download className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
