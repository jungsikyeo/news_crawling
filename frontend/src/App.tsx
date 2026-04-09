import { useState, useEffect, useCallback, useRef } from "react"
import { Sidebar } from "@/components/Sidebar"
import type { SidebarStatus } from "@/components/Sidebar"
import { NewsList } from "@/components/NewsList"
import { Analytics } from "@/components/Analytics"
import { History } from "@/components/History"
import { Scraps } from "@/components/Scraps"
import { ThemeSelector } from "@/components/ThemeSelector"
import { Modal } from "@/components/Modal"
import type { ModalType } from "@/components/Modal"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { startCrawl, stopCrawl, runOnce, fetchCrawlStatus, resetData } from "@/hooks/useApi"

interface ModalState {
  open: boolean
  type: ModalType
  title: string
  message: string
  onConfirm?: () => void
  autoCloseSeconds?: number
  onAutoClose?: () => void
}

function App() {
  const [crawlStatus, setCrawlStatus] = useState<SidebarStatus>({ running: false })
  const [modal, setModal] = useState<ModalState>({ open: false, type: "info", title: "", message: "" })
  const [activeTab, setActiveTab] = useState("articles")
  const runOnceWaiting = useRef(false)
  const prevRunning = useRef(false)
  const newsRefresh = useRef<(() => void) | null>(null)

  function showModal(type: ModalType, title: string, message: string) {
    setModal({ open: true, type, title, message })
  }

  const pollStatus = useCallback(async () => {
    try {
      const data = await fetchCrawlStatus()
      const s = data as {
        running?: boolean
        is_running?: boolean
        crawling_active?: boolean
        last_run?: string | null
        collected?: number
        total_count?: number
        new_count?: number
      }
      const isRunning = s.is_running ?? s.running ?? false
      const status: SidebarStatus = {
        running: s.crawling_active ?? isRunning,
        last_run: s.last_run ?? undefined,
        collected: s.total_count ?? s.collected,
        new_count: s.new_count,
      }
      setCrawlStatus(status)

      // 수집 완료 감지: running이 true→false로 변하면 목록 갱신
      if (prevRunning.current && !isRunning) {
        if (runOnceWaiting.current) {
          // 즉시수집: 완료 후 폴링 중지
          runOnceWaiting.current = false
          setPolling(false)
          setModal({
            open: true,
            type: "success",
            title: "수집 완료",
            message: `총 ${s.total_count ?? 0}건 수집, 신규 ${s.new_count ?? 0}건. 집계를 시작합니다.`,
            autoCloseSeconds: 3,
            onAutoClose: () => {
              setModal((m) => ({ ...m, open: false }))
              newsRefresh.current?.()
              setActiveTab("articles")
            },
          })
        } else {
          // 스케줄링: 목록 갱신 + 폴링 유지
          newsRefresh.current?.()
        }
      }
      prevRunning.current = isRunning
    } catch {
      // silently ignore poll errors
    }
  }, [])

  const [polling, setPolling] = useState(false)

  useEffect(() => {
    if (!polling) return
    const id = setInterval(() => { void pollStatus() }, 2000)
    return () => clearInterval(id)
  }, [polling, pollStatus])

  async function handleStartCrawl(data: {
    keywords: string[]
    portals: string[]
    interval: number
    search_from: string
  }) {
    try {
      await startCrawl(data)
      showModal("success", "크롤링 시작", `${data.keywords.join(", ")} 키워드로 ${data.interval}분 간격 수집을 시작합니다.`)
      setPolling(true)
      await pollStatus()
    } catch (e) {
      showModal("error", "시작 실패", e instanceof Error ? e.message : "크롤링 시작에 실패했습니다.")
    }
  }

  async function handleStopCrawl() {
    try {
      await stopCrawl()
      setPolling(false)
      showModal("info", "크롤링 중지", "크롤링이 중지되었습니다.")
      await pollStatus()
    } catch (e) {
      showModal("error", "중지 실패", e instanceof Error ? e.message : "크롤링 중지에 실패했습니다.")
    }
  }

  async function handleRunOnce(data: {
    keywords: string[]
    portals: string[]
    search_from: string
  }) {
    try {
      await runOnce(data)
      runOnceWaiting.current = true
      showModal("info", "즉시 수집", "수집을 시작했습니다. 완료되면 알려드립니다.")
      setPolling(true)
      await pollStatus()
    } catch (e) {
      showModal("error", "즉시 수집 실패", e instanceof Error ? e.message : "즉시 수집에 실패했습니다.")
    }
  }

  function handleReset() {
    setModal({
      open: true,
      type: "confirm",
      title: "데이터 초기화",
      message: "모든 뉴스 기사, 검색 히스토리가 삭제됩니다. 계속하시겠습니까?",
      onConfirm: async () => {
        try {
          await resetData()
          setModal({ open: false, type: "info", title: "", message: "" })
          window.location.reload()
        } catch (e) {
          showModal("error", "초기화 실패", e instanceof Error ? e.message : "초기화에 실패했습니다.")
        }
      },
    })
  }

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <Sidebar
        status={crawlStatus}
        onStartCrawl={handleStartCrawl}
        onStopCrawl={handleStopCrawl}
        onRunOnce={handleRunOnce}
        onWarning={(msg) => showModal("warning", "알림", msg)}
        onReset={handleReset}
      />

      <main className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-auto p-6">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <div className="flex items-center justify-between mb-6">
              <TabsList>
                <TabsTrigger value="articles">기사 목록</TabsTrigger>
                <TabsTrigger value="analytics">통계 분석</TabsTrigger>
                <TabsTrigger value="scraps">스크랩</TabsTrigger>
                <TabsTrigger value="history">히스토리</TabsTrigger>
              </TabsList>
              <ThemeSelector />
            </div>

            <TabsContent value="articles" className="animate-fade-up">
              <NewsList refreshRef={newsRefresh} />
            </TabsContent>

            <TabsContent value="analytics" className="animate-fade-up">
              <Analytics />
            </TabsContent>

            <TabsContent value="scraps" className="animate-fade-up">
              <Scraps />
            </TabsContent>

            <TabsContent value="history" className="animate-fade-up">
              <History />
            </TabsContent>
          </Tabs>
        </div>
      </main>

      <Modal
        open={modal.open}
        type={modal.type}
        title={modal.title}
        message={modal.message}
        onClose={() => setModal((m) => ({ ...m, open: false }))}
        onConfirm={modal.onConfirm}
        autoCloseSeconds={modal.autoCloseSeconds}
        onAutoClose={modal.onAutoClose}
      />
    </div>
  )
}

export default App
