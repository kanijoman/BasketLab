/**
 * DiffBadge — the REAL difference between a figure and what it is compared with (issue #608), with its sign and the decimals of the figure: ``+2.1``.
 *
 * It replaces the arrows of trend (⇈ ↑ ≈ ↓ ⇊): an arrow said «a lot or a little» by a threshold of percentage; the difference says how much. For a figure that is
 * already a percentage it is in percentage points. Green when it is good (up; down for «less is better» columns: pass ``reverse``), red when it is bad, grey when it is nothing.
 * It is the pill of its tone (`TONE_PILL`, AA over every surface, #856) over an opaque surface of its own: the cells it sits in are painted with the colour of their quartile, and green
 * or red text straight on them does not reach WCAG AA (#1199).
 */
import { cn } from '@/lib/utils'
import { TONE_PILL } from './tone'

/** ``+2.1`` / ``-2.55`` / ``0.0`` (a difference that rounds to nothing has no sign); null when a figure is missing. */
export function formatDiff(recent: number | null | undefined, reference: number | null | undefined, decimals = 1): string | null {
  if (recent == null || reference == null || Number.isNaN(recent) || Number.isNaN(reference)) return null
  const diff = recent - reference
  const text = Math.abs(diff).toFixed(decimals)
  if (Number(text) === 0) return (0).toFixed(decimals)
  return `${diff > 0 ? '+' : '-'}${text}`
}

interface Props {
  recent: number | null | undefined
  /** What it is compared with: the season, the other group... */
  season: number | null | undefined
  /** Columns where lower value = better (e.g. turnovers, defensive_rating) */
  reverse?: boolean
  decimals?: number
  className?: string
}

export default function DiffBadge({ recent, season, reverse = false, decimals = 1, className }: Props) {
  const text = formatDiff(recent, season, decimals)
  if (text === null) return null
  const diff = (recent as number) - (season as number)
  const none = Number(text) === 0
  const good = (diff > 0) !== reverse
  return (
    <span className={cn('inline-flex rounded bg-surface text-xs font-semibold tabular-nums', className)}>
      <span
        className={cn('inline-flex items-center rounded px-1', TONE_PILL[none ? 'neutral' : good ? 'ok' : 'bad'])}
        title={`${(recent as number).toFixed(decimals)} frente a ${(season as number).toFixed(decimals)}`}
      >
        {text}
      </span>
    </span>
  )
}
