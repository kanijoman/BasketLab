/**
 * StatCard — displays a single metric with an optional delta (the real difference with what it is compared with, issue #608).
 *
 * Usage:
 *   <StatCard label="Puntos/partido" value={82.4} delta={+1.2} />
 */
import { cn } from '@/lib/utils'
import { TONE_PANEL, type Tone } from './tone'

interface Props {
  label: string
  value: string | number
  /** Numeric delta (e.g. +1.2) shown with +/- sign */
  delta?: number
  /** Caption under the value */
  sub?: string
  /** The tone of the card (issue #190: the tones of the system) */
  tone?: Tone
  className?: string
  /** Optional click handler */
  onClick?: () => void
}

export default function StatCard({
  label,
  value,
  delta,
  sub,
  tone = 'neutral',
  className,
  onClick,
}: Props) {
  const deltaPositive = delta !== undefined && delta > 0
  const deltaNeutral  = delta !== undefined && delta === 0

  return (
    <div
      className={cn(
        'card p-4 flex flex-col gap-1 select-none',
        TONE_PANEL[tone],
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
