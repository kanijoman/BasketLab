/**
 * StatCard — displays a single metric with an optional delta (the real difference with what it is compared with, issue #608).
 *
 * Usage:
 *   <StatCard label="Puntos/partido" value={82.4} delta={+1.2} />
 */
import { cn } from '@/lib/utils'

interface Props {
  label: string
  value: string | number
  /** Numeric delta (e.g. +1.2) shown with +/- sign */
  delta?: number
  /** Caption under the value */
  sub?: string
  /** Accent color variant */
  accent?: 'green' | 'blue' | 'amber' | 'red' | 'default'
  className?: string
  /** Optional click handler */
  onClick?: () => void
}

const ACCENT_CLASSES: Record<NonNullable<Props['accent']>, string> = {
  green:   'border-ok/40 bg-ok/5',
  blue:    'border-secondary/40 bg-secondary/5',
  amber:   'border-warn/40 bg-warn/5',
  red:     'border-bad/40 bg-bad/5',
  default: 'border-line',
}

export default function StatCard({
  label,
  value,
  delta,
  sub,
  accent = 'default',
  className,
  onClick,
}: Props) {
  const deltaPositive = delta !== undefined && delta > 0
  const deltaNeutral  = delta !== undefined && delta === 0

  return (
    <div
      className={cn(
        'card p-4 flex flex-col gap-1 select-none',
        ACCENT_CLASSES[accent],
        onClick && 'cursor-pointer hover:border-accent/60 hover:bg-surface-raised transition-colors',
        className,
      )}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <span className="text-xs text-ink-muted uppercase tracking-wide truncate">
        {label}
      </span>

      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold text-ink tabular-nums">
          {value}
        </span>

        {delta !== undefined && (
          <span
            className={cn(
              'text-xs font-medium tabular-nums',
              deltaPositive ? 'text-ok' : deltaNeutral ? 'text-ink-faint' : 'text-bad',
            )}
          >
            {deltaPositive ? '+' : ''}{delta.toFixed(1)}
          </span>
        )}
      </div>

      {sub && (
        <span className="text-xs text-ink-faint">{sub}</span>
      )}
    </div>
  )
}
