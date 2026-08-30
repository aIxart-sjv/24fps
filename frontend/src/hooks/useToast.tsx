import * as ToastPrimitive from '@radix-ui/react-toast'
import { CheckCircle2, AlertTriangle, XCircle, Info } from 'lucide-react'
import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

type ToastTone = 'success' | 'warning' | 'error' | 'info'

interface ToastItem {
  id: number
  title: string
  description?: string
  tone: ToastTone
}

interface ToastContextValue {
  notify: (title: string, options?: { description?: string; tone?: ToastTone }) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const ICONS: Record<ToastTone, typeof CheckCircle2> = {
  success: CheckCircle2,
  warning: AlertTriangle,
  error: XCircle,
  info: Info,
}

const TONE_COLOR: Record<ToastTone, string> = {
  success: 'text-success',
  warning: 'text-warning',
  error: 'text-critical',
  info: 'text-info',
}

let idCounter = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const notify = useCallback((title: string, options?: { description?: string; tone?: ToastTone }) => {
    const id = ++idCounter
    setToasts((prev) => [...prev, { id, title, description: options?.description, tone: options?.tone ?? 'info' }])
  }, [])

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ notify }}>
      <ToastPrimitive.Provider swipeDirection="right" duration={4000}>
        {children}
        {toasts.map((toast) => {
          const Icon = ICONS[toast.tone]
          return (
            <ToastPrimitive.Root
              key={toast.id}
              onOpenChange={(open) => !open && remove(toast.id)}
              className="flex items-start gap-3 rounded-lg border border-border bg-surface-elevated p-3.5 shadow-2xl data-[state=open]:animate-slide-in data-[swipe=end]:translate-x-full"
            >
              <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', TONE_COLOR[toast.tone])} />
              <div className="min-w-0">
                <ToastPrimitive.Title className="text-sm font-medium text-fg">{toast.title}</ToastPrimitive.Title>
                {toast.description && (
                  <ToastPrimitive.Description className="mt-0.5 text-xs text-fg-muted">
                    {toast.description}
                  </ToastPrimitive.Description>
                )}
              </div>
            </ToastPrimitive.Root>
          )
        })}
        <ToastPrimitive.Viewport className="fixed bottom-4 right-4 z-[100] flex w-96 max-w-full flex-col gap-2 outline-none" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
