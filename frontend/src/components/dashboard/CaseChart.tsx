import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip as RechartsTooltip } from 'recharts'
import type { Case } from '@/services/types'

const STATUS_COLORS: Record<string, string> = {
  Active: '#22d3ee',
  'Under Review': '#f59e0b',
  Draft: '#71717a',
  Closed: '#3f3f46',
}

export function CaseChart({ cases }: { cases: Case[] }) {
  const counts = cases.reduce<Record<string, number>>((acc, c) => {
    acc[c.status] = (acc[c.status] ?? 0) + 1
    return acc
  }, {})
  const data = Object.entries(counts).map(([status, count]) => ({ status, count }))
  const total = cases.length

  return (
    <div className="flex items-center gap-6">
      <div className="relative h-40 w-40 shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="count"
              nameKey="status"
              innerRadius={48}
              outerRadius={70}
              paddingAngle={3}
              stroke="none"
              isAnimationActive={false}
            >
              {data.map((entry) => (
                <Cell key={entry.status} fill={STATUS_COLORS[entry.status] ?? '#71717a'} />
              ))}
            </Pie>
            <RechartsTooltip
              contentStyle={{
                background: '#18181b',
                border: '1px solid #27272a',
                borderRadius: 6,
                fontSize: 12,
              }}
              itemStyle={{ color: '#f4f4f5' }}
              labelStyle={{ color: '#a1a1aa' }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono text-2xl font-semibold tabular-nums text-fg">{total}</span>
          <span className="text-[10px] uppercase tracking-wide text-fg-subtle">Total</span>
        </div>
      </div>
      <div className="flex-1 space-y-2.5">
        {data.map((entry) => (
          <div key={entry.status} className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: STATUS_COLORS[entry.status] ?? '#71717a' }} />
              <span className="text-fg-muted">{entry.status}</span>
            </div>
            <span className="font-mono font-medium text-fg">{entry.count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
