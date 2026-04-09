import { useEffect, useState as useReactState } from "react"
import { createPortal } from "react-dom"
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react"
import { Button } from "@/components/ui/button"

export type ModalType = "success" | "error" | "warning" | "info" | "confirm"

interface ModalProps {
  open: boolean
  type?: ModalType
  title?: string
  message: string
  onClose: () => void
  onConfirm?: () => void
  autoCloseSeconds?: number
  onAutoClose?: () => void
}

const iconMap = {
  success: { icon: CheckCircle2, bgClass: "bg-green-500/10", iconClass: "text-green-500" },
  error: { icon: AlertTriangle, bgClass: "bg-destructive/10", iconClass: "text-destructive" },
  warning: { icon: AlertTriangle, bgClass: "bg-amber-500/10", iconClass: "text-amber-500" },
  info: { icon: Info, bgClass: "bg-primary/10", iconClass: "text-primary" },
  confirm: { icon: AlertTriangle, bgClass: "bg-red-500/20", iconClass: "text-red-500" },
}

export function Modal({ open, type = "info", title, message, onClose, onConfirm, autoCloseSeconds, onAutoClose }: ModalProps) {
  const [countdown, setCountdown] = useReactState(autoCloseSeconds ?? 0)

  useEffect(() => {
    if (!open || !autoCloseSeconds) return
    setCountdown(autoCloseSeconds)
    const id = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(id)
          onAutoClose?.()
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(id)
  }, [open, autoCloseSeconds])

  if (!open) return null

  const { icon: Icon, bgClass, iconClass } = iconMap[type]
  const isConfirm = type === "confirm"

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 backdrop-blur-md"
      onClick={(e) => { if (e.target === e.currentTarget && !autoCloseSeconds) onClose() }}
    >
      <div className="bg-white dark:bg-zinc-900 border border-border rounded-xl p-6 shadow-2xl max-w-sm w-full mx-4 animate-fade-up">
        <div className="flex items-start gap-3 mb-4">
          <div className={`h-10 w-10 rounded-full ${bgClass} flex items-center justify-center flex-shrink-0`}>
            <Icon className={`h-5 w-5 ${iconClass}`} />
          </div>
          <div className="flex-1 min-w-0">
            {title && <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-1">{title}</p>}
            <p className="text-sm text-zinc-700 dark:text-zinc-300">{message}</p>
            {autoCloseSeconds && countdown > 0 && (
              <p className="text-xs text-primary mt-2 font-medium">
                {countdown}초 후 기사 목록으로 이동합니다...
              </p>
            )}
          </div>
          {!autoCloseSeconds && (
            <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors flex-shrink-0">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        {!autoCloseSeconds && (
          <div className="flex justify-end gap-2">
            {isConfirm && (
              <Button size="sm" variant="outline" onClick={onClose}>
                취소
              </Button>
            )}
            <Button
              size="sm"
              variant={isConfirm ? "destructive" : "default"}
              onClick={isConfirm ? onConfirm : onClose}
            >
              확인
            </Button>
          </div>
        )}
      </div>
    </div>,
    document.body
  )
}
