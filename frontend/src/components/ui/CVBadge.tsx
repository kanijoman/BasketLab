/**
 * CVBadge — intra-team game-to-game variability indicator.
 *
 * Shows as a tiny "σ XX%" chip next to a stat value, colour-coded by severity:
 *   CV < 15 %  → slate/dim   (consistent, predictable)
 *   CV 15-30 % → amber       (moderate variance)
 *   CV > 30 %  → red         (high variance, volatile)
 *
 * Hovering reveals std dev and mean alongside the interpretation.
 */
import Tooltip from '@/components/ui/Tooltip'

export interface CVEntry {
  mean: number
  std: number
  cv: number
  n: number
}

interface CVBadgeProps {
  entry: CVEntry
  /** Thresholds [low, high] for colour coding.
   *  Default [15, 30] suits team-level stats; use [50, 100] for players. */
  thresholds?: [number, number]
}

/** Returns Tailwind classes for the pill background + text so it remains
 *  readable on any quartile cell background (green Q1 through red Q4). */
function cvClass(cv: number, thresholds: [number, number]): string {
  if (cv >= thresholds[1]) return 'bg-bad/15 text-bad ring-1 ring-bad/30'
  if (cv >= thresholds[0]) return 'bg-warn/15 text-warn ring-1 ring-warn/30'
  return 'bg-surface text-ink-muted ring-1 ring-line'
}

function cvLabel(cv: number, thresholds: [number, number]): string {
  if (cv >= thresholds[1]) return 'Alta variabilidad'
  if (cv >= thresholds[0]) return 'Variabilidad moderada'
  return 'Consistente'
}

export default function CVBadge({ entry, thresholds = [15, 30] }: CVBadgeProps) {
  const { mean, std, cv, n } = entry
  const tipText =
    `${cvLabel(cv, thresholds)} partido a partido\n` +
    `Media: ${mean.toFixed(1)}  ·  σ: ${std.toFixed(1)}  ·  CV: ${cv.toFixed(1)}%\n` +
    `(sobre ${n} partidos)`

  return (
    <Tooltip text={tipText}>
      <span className={`inline-block px-1 rounded text-[10px] font-mono leading-none ${cvClass(cv, thresholds)}`}>
        σ{cv.toFixed(0)}%
      </span>
    </Tooltip>
  )
}
