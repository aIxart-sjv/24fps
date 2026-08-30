import { CircleDot } from 'lucide-react'
import { cn } from '@/lib/utils'

export function DemoModeBadge({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'flex items-center gap-1.5 rounded border border-accent/20 bg-accent/5 px-2 py-1.5 text-[10px] font-medium uppercase tracking-wider text-accent',
        className,
      )}
      title="Interactive prototype running on simulated forensic data"
    >
      <CircleDot className="h-3 w-3 shrink-0" />
      Demo Mode
      <span className="ml-auto normal-case tracking-normal text-fg-subtle">Mock data</span>
    </div>
  )
}
