import { useEffect, useRef, useState } from "react"
import { Loader2, AlertCircle } from "lucide-react"

// @rhwp/core는 WASM 기반이므로 최초 로드 시 init 필요
// Vite의 ?url import로 WASM 번들을 asset으로 처리
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore — Vite asset import
import wasmUrl from "@rhwp/core/rhwp_bg.wasm?url"
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore — NoLegal types on default init export
import init, { HwpDocument } from "@rhwp/core"

let wasmReady: Promise<unknown> | null = null

function ensureWasm() {
  if (!wasmReady) {
    // rhwp WASM이 요구하는 브라우저 shim
    const g = globalThis as unknown as { measureTextWidth?: (font: string, text: string) => number }
    if (typeof g.measureTextWidth !== "function") {
      g.measureTextWidth = (font: string, text: string) => {
        const canvas = document.createElement("canvas")
        const ctx = canvas.getContext("2d")
        if (!ctx) return 0
        ctx.font = font
        return ctx.measureText(text).width
      }
    }
    wasmReady = init({ module_or_path: wasmUrl })
  }
  return wasmReady
}

interface HwpViewerProps {
  blob: Blob
  filename: string
}

export function HwpViewer({ blob, filename }: HwpViewerProps) {
  if (filename.endsWith(".txt")) {
    return <TxtViewer blob={blob} />
  }
  return <HwpRenderer blob={blob} />
}

function HwpRenderer({ blob }: { blob: Blob }) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pages, setPages] = useState<string[]>([])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setPages([])

    ;(async () => {
      try {
        await ensureWasm()
        const buffer = await blob.arrayBuffer()
        const data = new Uint8Array(buffer)
        const doc = new HwpDocument(data)
        const count = doc.pageCount()
        const svgs: string[] = []
        for (let i = 0; i < count; i++) {
          svgs.push(doc.renderPageSvg(i))
        }
        doc.free?.()
        if (!cancelled) {
          setPages(svgs)
          setLoading(false)
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "미리보기를 생성할 수 없습니다.")
          setLoading(false)
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [blob])

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-20 text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="text-sm">HWP 렌더링 중...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-20">
        <AlertCircle className="h-8 w-8 text-destructive" />
        <p className="text-sm text-destructive">{error}</p>
        <p className="text-xs text-muted-foreground">rhwp 뷰어가 이 문서를 렌더링하지 못했습니다.</p>
      </div>
    )
  }

  if (pages.length === 0) {
    return (
      <div className="py-20 text-center text-sm text-muted-foreground">
        페이지가 없습니다.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 items-center bg-muted p-4 rounded-md">
      {pages.map((svg, i) => (
        <div
          key={i}
          className="rhwp-page bg-white shadow-lg overflow-hidden"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      ))}
    </div>
  )
}

function TxtViewer({ blob }: { blob: Blob }) {
  const [text, setText] = useState<string>("")
  const [loading, setLoading] = useState(true)
  const ref = useRef<HTMLPreElement>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    ;(async () => {
      const t = await blob.text()
      if (!cancelled) {
        setText(t)
        setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [blob])

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-20 text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="text-sm">불러오는 중...</span>
      </div>
    )
  }

  return (
    <pre
      ref={ref}
      className="whitespace-pre-wrap break-words text-sm font-mono bg-card rounded-md p-4 border border-border/50 leading-relaxed"
    >
      {text}
    </pre>
  )
}
