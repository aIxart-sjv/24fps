import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export const TooltipProvider = TooltipPrimitive.Provider

export function Tooltip({ content, children, className }: { content: ReactNode; children: ReactNode; className?: string }) {
  return (
    <TooltipPrimitive.Root delayDuration={200}>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          sideOffset={6}
          className={cn(
            'z-50 rounded border border-border bg-surface-elevated px-2.5 py-1.5 text-xs text-fg shadow-lg animate-fade-in',
            className,
          )}
        >
          {content}
          <TooltipPrimitive.Arrow className="fill-surface-elevated" />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  )
}
