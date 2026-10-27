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
  green:   'border-brand-600/40 bg-brand-600/5',
  blue:    'border-accent-600/40 bg-accent-600/5',
  amber:   'border-warn/40 bg-warn/5',
  red:     'border-down/40 bg-down/5',
  default: 'border-surface-border',
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
        onClick && 'cursor-pointer hover:border-brand-600/60 hover:bg-surface-hover transition-colors',
        className,
      )}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <span className="text-xs text-ink-secondary uppercase tracking-wide truncate">
        {label}
      </span>

      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold text-ink-primary tabular-nums">
          {value}
        </span>

        {delta !== undefined && (
          <span
            className={cn(
              'text-xs font-medium tabular-nums',
              deltaPositive ? 'text-brand-400' : deltaNeutral ? 'text-ink-muted' : 'text-down',
            )}
          >
            {deltaPositive ? '+' : ''}{delta.toFixed(1)}
          </span>
        )}
      </div>

      {sub && (
        <span className="text-xs text-ink-muted">{sub}</span>
      )}
    </div>
  )
}
