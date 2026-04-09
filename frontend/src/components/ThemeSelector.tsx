import { useState, useEffect, useRef } from "react"
import { Check, Palette } from "lucide-react"

const THEMES = [
  { id: "midnight", label: "Midnight", color: "#6366f1", group: "dark" },
  { id: "emerald", label: "Emerald", color: "#10b981", group: "dark" },
  { id: "rose", label: "Rose", color: "#f43f5e", group: "dark" },
  { id: "amber", label: "Amber", color: "#f59e0b", group: "dark" },
  { id: "ocean", label: "Ocean", color: "#0ea5e9", group: "dark" },
  { id: "light", label: "Light", color: "#6366f1", group: "light" },
  { id: "paper", label: "Paper", color: "#ea580c", group: "light" },
  { id: "arctic", label: "Arctic", color: "#0ea5e9", group: "light" },
] as const

type ThemeId = (typeof THEMES)[number]["id"]

const STORAGE_KEY = "news-dashboard-theme"

function applyTheme(id: ThemeId) {
  document.documentElement.setAttribute("data-theme", id)
  localStorage.setItem(STORAGE_KEY, id)
}

export function ThemeSelector() {
  const [current, setCurrent] = useState<ThemeId>(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as ThemeId | null
    return stored ?? "midnight"
  })
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    applyTheme(current)
  }, [current])

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [])

  function select(id: ThemeId) {
    setCurrent(id)
    setOpen(false)
  }

  const activeTheme = THEMES.find((t) => t.id === current)!

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-1.5 text-sm text-foreground hover:bg-secondary transition-colors"
      >
        <span
          className="h-3.5 w-3.5 rounded-full flex-shrink-0 ring-1 ring-white/10"
          style={{ backgroundColor: activeTheme.color }}
        />
        <Palette className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="capitalize text-xs font-medium">{activeTheme.label}</span>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1.5 z-50 min-w-[170px] rounded-lg border border-border bg-popover py-1.5 shadow-xl animate-fade-up" style={{ backdropFilter: "none", opacity: 1, backgroundColor: "hsl(var(--popover))" }}>
          <p className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Dark</p>
          {THEMES.filter(t => t.group === "dark").map((theme) => (
            <button
              key={theme.id}
              onClick={() => select(theme.id)}
              className={[
                "flex w-full items-center gap-2.5 px-3 py-1.5 text-sm transition-colors hover:bg-secondary",
                current === theme.id
                  ? "text-foreground font-medium"
                  : "text-muted-foreground",
              ].join(" ")}
            >
              <span
                className="h-3 w-3 rounded-full flex-shrink-0 ring-1 ring-black/10"
                style={{ backgroundColor: theme.color }}
              />
              <span className="flex-1 text-left text-xs">{theme.label}</span>
              {current === theme.id && (
                <Check className="h-3 w-3 text-primary flex-shrink-0" />
              )}
            </button>
          ))}
          <div className="my-1 border-t border-border" />
          <p className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Light</p>
          {THEMES.filter(t => t.group === "light").map((theme) => (
            <button
              key={theme.id}
              onClick={() => select(theme.id)}
              className={[
                "flex w-full items-center gap-2.5 px-3 py-1.5 text-sm transition-colors hover:bg-secondary",
                current === theme.id
                  ? "text-foreground font-medium"
                  : "text-muted-foreground",
              ].join(" ")}
            >
              <span
                className="h-3 w-3 rounded-full flex-shrink-0 ring-1 ring-black/10"
                style={{ backgroundColor: theme.color }}
              />
              <span className="flex-1 text-left text-xs">{theme.label}</span>
              {current === theme.id && (
                <Check className="h-3 w-3 text-primary flex-shrink-0" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
