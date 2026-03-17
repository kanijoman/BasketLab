/**
 * TrendBadge — shows a trend arrow comparing a recent value to a baseline.
 *
 * Direction thresholds (match Qt TrendCalculator):
 *   >+10%  → ⇈  (great)
 *   +5–10% → ↑  (good)
 *   ±5%    → ≈  (flat)
 *   -5–10% → ↓  (bad)
 *   <-10%  → ⇊  (poor)
 *
 * For "lower is better" columns pass reverse=true.
 */
import { cn } from '@/lib/utils'

interface Props {
  recent:   number | null | undefined
  season:   number | null | undefined
  /** Columns where lower value = better (e.g. turnovers, defensive_rating) */
  reverse?: boolean
  className?: string
}

type Level = 'great' | 'good' | 'flat' | 'bad' | 'poor'

function level(pct: number, reverse: boolean): Level {
  const signed = reverse ? -pct : pct
  if (signed >  10) return 'great'
  if (signed >   5) return 'good'
  if (signed > - 5) return 'flat'
  if (signed > -10) return 'bad'
  return 'poor'
}

const ARROW: Record<Level, string> = {
  great: '⇈',
  good:  '↑',
  flat:  '≈',
  bad:   '↓',
  poor:  '⇊',
}

const COLOR: Record<Level, string> = {
  great: 'text-brand-400',
  good:  'text-brand-500',
  flat:  'text-ink-secondary',
  bad:   'text-warn',
  poor:  'text-down',
}

export default function TrendBadge({ recent, season, reverse = false, className }: Props) {
  if (recent == null || season == null || season === 0) return null

  const pct = ((recent - season) / Math.abs(season)) * 100
  const lvl = level(pct, reverse)
  const sign = pct > 0 ? '+' : ''

  return (
    <span
      className={cn('inline-flex items-center gap-0.5 text-xs font-semibold tabular-nums', COLOR[lvl], className)}
      title={`Reciente: ${recent.toFixed(1)} | Temporada: ${season.toFixed(1)} (${sign}${pct.toFixed(1)}%)`}
    >
      <span>{ARROW[lvl]}</span>
      <span className="text-[10px] opacity-80">{sign}{Math.abs(pct).toFixed(0)}%</span>
    </span>
  )
}
