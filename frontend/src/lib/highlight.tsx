import type React from "react"

const HIGHLIGHT_STYLES: Record<string, React.CSSProperties> = {
  keyword: { backgroundColor: "var(--highlight-keyword)", borderRadius: "2px", padding: "0 2px", color: "inherit", fontWeight: 600 },
  search: { backgroundColor: "rgba(251,191,36,0.35)", borderRadius: "2px", padding: "0 2px", color: "inherit", fontWeight: 600 },
}

export function highlightText(text: string, highlights: { term: string; styleKey: string }[]) {
  if (!text || highlights.every((h) => !h.term)) return text

  const activeHighlights = highlights.filter((h) => h.term)
  const pattern = activeHighlights
    .map((h) => h.term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|")
  if (!pattern) return text

  const regex = new RegExp(`(${pattern})`, "gi")
  const parts = text.split(regex)

  return parts.map((part, i) => {
    for (const h of activeHighlights) {
      if (part.toLowerCase() === h.term.toLowerCase()) {
        return <mark key={i} style={HIGHLIGHT_STYLES[h.styleKey]}>{part}</mark>
      }
    }
    return part
  })
}
