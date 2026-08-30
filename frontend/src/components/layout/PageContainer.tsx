import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function PageContainer({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('mx-auto max-w-[1600px] px-6 py-6', className)}>{children}</div>
}
