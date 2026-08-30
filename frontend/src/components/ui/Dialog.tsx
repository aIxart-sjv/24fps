import * as DialogPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface DialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  children: ReactNode
  variant?: 'modal' | 'panel'
}

export function Dialog({ open, onOpenChange, title, description, children, variant = 'modal' }: DialogProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/60 animate-fade-in" />
        <DialogPrimitive.Content
          className={cn(
            'fixed z-50 flex flex-col border-border bg-surface shadow-2xl focus:outline-none',
            variant === 'modal' &&
              'left-1/2 top-1/2 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-lg border animate-fade-in',
            variant === 'panel' &&
              'right-0 top-0 h-full w-full max-w-md border-l animate-slide-in',
          )}
        >
          <div className="flex items-start justify-between border-b border-border px-5 py-4">
            <div>
              <DialogPrimitive.Title className="text-sm font-semibold text-fg">{title}</DialogPrimitive.Title>
              {description && (
                <DialogPrimitive.Description className="mt-1 text-xs text-fg-muted">
                  {description}
                </DialogPrimitive.Description>
              )}
            </div>
            <DialogPrimitive.Close className="rounded p-1 text-fg-subtle hover:bg-surface-elevated hover:text-fg">
              <X className="h-4 w-4" />
            </DialogPrimitive.Close>
          </div>
          <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
